# SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
# SPDX-License-Identifier: GPL-3.0-or-later


# This module file uses code from the following files in the official
# Ansible repo:
# * <https://github.com/ansible/ansible/raw/devel/lib/ansible/modules/package_facts.py>
#
# Since the file listed above is a module, it is licensed with
# GPL-3.0-or-later; this file, in turn, is licensed as such even though
# Ansible convention is to license module_utils with BSD-2-Clause.
#
# The original copyright notice is as follows:

# (c) 2017, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# (Also, here's a comment preserved from the original module):
# most of it copied from AWX's scan_packages module


from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re

from ansible.module_utils.common.text.converters import to_native, to_text
from ansible.module_utils.basic import missing_required_lib
from ansible.module_utils.common.locale import get_best_parsable_locale
from ansible.module_utils.common.process import get_bin_path
from ansible.module_utils.common.respawn import has_respawned, probe_interpreters_for_module, respawn_module

from ansible_collections.plugins.module_utils.facts.packages import LibMgr, CLIMgr, get_all_pkg_managers


class RPM(LibMgr):

    requires_module = True      # for warning if library isn't found
    LIB = 'rpm'

    def list_installed(self):
        return self._lib.TransactionSet().dbMatch()

    def get_package_details(self, package):
        return dict(name=package[self._lib.RPMTAG_NAME],
                    version=package[self._lib.RPMTAG_VERSION],
                    release=package[self._lib.RPMTAG_RELEASE],
                    epoch=package[self._lib.RPMTAG_EPOCH],
                    arch=package[self._lib.RPMTAG_ARCH],)

    def is_available(self):
        '''we expect the python bindings installed, but this gives
        warning if they are missing and we have rpm cli'''

        we_have_lib = super(RPM, self).is_available()

        try:
            get_bin_path('rpm')

            if not we_have_lib and not has_respawned():
                # try to locate an interpreter with the necessary lib
                interpreters = ['/usr/libexec/platform-python',
                                '/usr/bin/python3',
                                '/usr/bin/python2']
                interpreter_path = probe_interpreters_for_module(interpreters, self.LIB)
                if interpreter_path:
                    respawn_module(interpreter_path)
                    # end of the line for this process; this module will exit when the respawned copy completes

            if not we_have_lib:
                self.module.warn('Found "rpm" but %s' % (missing_required_lib(self.LIB)))
        except ValueError:
            pass

        return we_have_lib

    def search_pkg_substr(self, substr):
        pass


class APT(LibMgr):

    requires_module = True      # for warning if library isn't found
    LIB = 'apt'

    def __init__(self, module=None):
        self._cache = None
        super(APT, self).__init__()

    @property
    def pkg_cache(self):
        if self._cache is not None:
            return self._cache

        self._cache = self._lib.Cache()
        return self._cache

    def is_available(self):
        '''we expect the python bindings installed, but if there is
        apt/apt-get give warning about missing bindings'''

        we_have_lib = super(APT, self).is_available()
        if not we_have_lib:
            for exe in ('apt', 'apt-get', 'aptitude'):
                try:
                    get_bin_path(exe)
                except ValueError:
                    continue
                else:
                    if not has_respawned():
                        # try to locate an interpreter with the necessary lib
                        interpreters = ['/usr/bin/python3',
                                        '/usr/bin/python2']
                        interpreter_path = probe_interpreters_for_module(interpreters, self.LIB)
                        if interpreter_path:
                            respawn_module(interpreter_path)
                            # end of the line for this process; this module will exit here when respawned copy completes

                    self.module.warn('Found "%s" but %s' % (exe, missing_required_lib('apt')))
                    break

        return we_have_lib

    def list_installed(self):
        # Store the cache to avoid running pkg_cache() for each item in the comprehension, which is very slow
        cache = self.pkg_cache
        return [pk for pk in cache.keys() if cache[pk].is_installed]

    def get_package_details(self, package):
        ac_pkg = self.pkg_cache[package].installed
        return dict(name=package, version=ac_pkg.version, arch=ac_pkg.architecture, category=ac_pkg.section, origin=ac_pkg.origins[0].origin)

    def search_pkg_substr(self, substr):
        pass


class PACMAN(CLIMgr):

    CLI = 'pacman'

    def list_installed(self):
        locale = get_best_parsable_locale(self.module)
        rc, out, err = self.module.run_command([self._cli, '-Qi'], environ_update=dict(LC_ALL=locale))
        if rc != 0 or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.split("\n\n")[:-1]

    def get_package_details(self, package):
        # parse values of details that might extend over several lines
        raw_pkg_details = {}
        last_detail = None
        for line in package.splitlines():
            m = re.match(r"([\w ]*[\w]) +: (.*)", line)
            if m:
                last_detail = m.group(1)
                raw_pkg_details[last_detail] = m.group(2)
            else:
                # append value to previous detail
                raw_pkg_details[last_detail] = raw_pkg_details[last_detail] + "  " + line.lstrip()

        provides = None
        if raw_pkg_details['Provides'] != 'None':
            provides = [
                p.split('=')[0]
                for p in raw_pkg_details['Provides'].split('  ')
            ]

        return {
            'name': raw_pkg_details['Name'],
            'version': raw_pkg_details['Version'],
            'arch': raw_pkg_details['Architecture'],
            'provides': provides,
        }

    def search_pkg_substr(self, substr):
        pass


class PKG(CLIMgr):

    CLI = 'pkg'
    atoms = ['name', 'version', 'origin', 'installed', 'automatic', 'arch', 'category', 'prefix', 'vital']

    def list_installed(self):
        rc, out, err = self.module.run_command([self._cli, 'query', "%%%s" % '\t%'.join(['n', 'v', 'R', 't', 'a', 'q', 'o', 'p', 'V'])])
        if rc != 0 or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.splitlines()

    def get_package_details(self, package):

        pkg = dict(zip(self.atoms, package.split('\t')))

        if 'arch' in pkg:
            try:
                pkg['arch'] = pkg['arch'].split(':')[2]
            except IndexError:
                pass

        if 'automatic' in pkg:
            pkg['automatic'] = bool(int(pkg['automatic']))

        if 'category' in pkg:
            pkg['category'] = pkg['category'].split('/', 1)[0]

        if 'version' in pkg:
            if ',' in pkg['version']:
                pkg['version'], pkg['port_epoch'] = pkg['version'].split(',', 1)
            else:
                pkg['port_epoch'] = 0

            if '_' in pkg['version']:
                pkg['version'], pkg['revision'] = pkg['version'].split('_', 1)
            else:
                pkg['revision'] = '0'

        if 'vital' in pkg:
            pkg['vital'] = bool(int(pkg['vital']))

        return pkg

    def search_pkg_substr(self, substr):
        pass


class PORTAGE(CLIMgr):

    CLI = 'qlist'
    atoms = ['category', 'name', 'version', 'ebuild_revision', 'slots', 'prefixes', 'sufixes']

    def list_installed(self):
        rc, out, err = self.module.run_command(' '.join([self._cli, '-Iv', '|', 'xargs', '-n', '1024', 'qatom']), use_unsafe_shell=True)
        if rc != 0:
            raise RuntimeError("Unable to list packages rc=%s : %s" % (rc, to_native(err)))
        return out.splitlines()

    def get_package_details(self, package):
        return dict(zip(self.atoms, package.split()))

    def search_pkg_substr(self, substr):
        pass


class APK(CLIMgr):

    CLI = 'apk'

    def list_installed(self):
        rc, out, err = self.module.run_command([self._cli, 'info', '-v'])
        if rc != 0 or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.splitlines()

    def get_package_details(self, package):
        raw_pkg_details = {'name': package, 'version': '', 'release': ''}
        nvr = package.rsplit('-', 2)
        try:
            return {
                'name': nvr[0],
                'version': nvr[1],
                'release': nvr[2],
            }
        except IndexError:
            return raw_pkg_details

    def search_pkg_substr(self, substr):
        pass


class PKG_INFO(CLIMgr):

    CLI = 'pkg_info'

    def list_installed(self):
        rc, out, err = self.module.run_command([self._cli, '-a'])
        if rc != 0 or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.splitlines()

    def get_package_details(self, package):
        raw_pkg_details = {'name': package, 'version': ''}
        details = package.split(maxsplit=1)[0].rsplit('-', maxsplit=1)

        try:
            return {
                'name': details[0],
                'version': details[1],
            }
        except IndexError:
            return raw_pkg_details

    def search_pkg_substr(self, substr):
        pass
