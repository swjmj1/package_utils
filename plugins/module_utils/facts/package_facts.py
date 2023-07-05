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
from functools import wraps

from ansible.module_utils.common.text.converters import to_native, to_text
from ansible.module_utils.basic import missing_required_lib
from ansible.module_utils.common.locale import get_best_parsable_locale
from ansible.module_utils.common.process import get_bin_path
from ansible.module_utils.common.respawn import has_respawned, probe_interpreters_for_module, respawn_module

from ansible_collections.swjmj1.package_utils.plugins.module_utils.facts.packages import LibMgr, CLIMgr, get_all_pkg_managers


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
        """Search for substr via pacman -Ss. Return info for each match.

        Since options "-s" (search) and "-i" (info) cannot be used
        together, find matching packages via "-s" first, then return
        info on each match via "-i".

        `pacman -Ss` outputs two lines for each matching package, with
        the package's repo, name, and version on the first line, then
        its description indented on the next line (and so on), like so:
            core/python 3.1.3-2
                Next generation of the python...
            ...

        `pacman -Si` outputs blocks in a "key: value" format like so:
            Repository      : core
            Name            : python
            ...

        Raise an exception if either `pacman -Ss` or `pacman -Si` fails.
        However, note that failure to find a matching package is, in
        this case, an expected possibility for `-Ss`, so no exception is
        raised in that situation -- but for `-Si`, an exception IS
        raised upon failure to find a matching package.

        Also, raise an exception if for some reason `-Ss` produces
        output different from its usual format.
        """

        locale = get_best_parsable_locale(self.module)
        rc, out, err = self.module.run_command(
            [self._cli, '-Ss', substr],
            environ_update=dict(LC_ALL=locale)
        )

        if (out != "" and rc != 0) or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        elif out == "":
            return []

        search_results = out.splitlines()
        if len(search_results) % 2 != 0:
            raise Exception('Unexpected output when searching for "%s":\n\n%s'
                    % (substr, out))

        info = []
        for line in search_results[::2]:
            repo_and_name = line.split()[0]     # exclude the version number
            rc, out, err = self.module.run_command(
                [self._cli, '-Si', repo_and_name],
                environ_update=dict(LC_ALL=locale)
            )
            if rc != 0 or err:
                raise Exception(
                    'Unable to get info about package "%s" rc=%s : %s'
                    % (repo_and_name, rc, err)
                )
            info.append(out)
        return info


class PKG(CLIMgr):

    CLI = 'pkg'
    atoms = ['name', 'version', 'origin', 'installed', 'automatic', 'arch', 'category', 'prefix', 'vital']

    # These are the output fields that `pkg search` shares with `pkg
    # info`; if a field exists here, then it also exists in
    # "self.atoms".
    search_output_fields = ['name', 'version', 'repository', 'arch', 'prefix']

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
        """Search for substr via `pkg search`.

        (For context, `pkg query` can only search installed packages.)

        Return a string containing a tab-separated list of output
        values, ordered as expected by method "get_package_details".

        Include in the returned string only the package info that can be
        output by both `pkg query` and `pkg search`. If a value expected
        by "get_package_details" is absent, then put an empty string
        where expected in the list, such that using "split()" on the
        returned string results in an empty string at its designated
        index.

        Issue a module warning if any line of output from `pkg search`
        has a format that doesn't consist of a requested field and its
        associated value; this might indicate a change in `pkg search`
        output, which should be brought to attention.
        """

        rc, out, err = self.module.run_command([
            self._cli,
            'search',
            '--search=pkg-name',
            '-U',           # don't update the repo catalogue every search
            *['--query-modifier=%s' % f for f in self.search_output_fields],
            substr,
        ])
        if rc != 0 or err:
            raise Exception('Unable to search for package "%s" rc=%s : %s' 
                            % (substr, rc, err))

        # Put lines into a tab-separated list in the order expected by
        # "get_package_details". Filter out unexpected lines.
        output_fields = [""] * len(self.atoms)
        for line in out.splitlines():
            try:
                field, value = re.split(line, r"\s*:\s*", maxsplit=1)
                atom_name = field.lower()

                # We get the "comment" field (i.e. package description)
                # whether we like it or not.
                if atom_name == "comment":
                    continue
                index = self.atoms.index(atom_name)
                output_fields[index] = value
            except ValueError:
                module.warn("Unexpected output from `pkg search`: %s" % line)
        return "\t".join(output_fields)


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
        rc, out, err = self.module.run_command([
            self._cli, 'search', substr,
        ])
        if rc != 0 or err:
            raise Exception("Unable to list packages rc=%s : %s" % (rc, err))
        return out.splitlines()


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


def for_each_pkg_mgr(fn):
    """Call function "fn" for each package manager found on the system.

    For modules dealing with package managers, use this as a decorator
    on the main function to avoid reinventing the process of finding
    package managers available on the system. "fn" should perform its
    module's unique functionality upon the calling code's AnsibleModule
    object, using the methods of the given PkgMgr object as needed; it
    should also update the given dict of results as appropriate for the
    module in question.

    Accordingly, "fn" must take the following arguments:
      module -- the calling code's AnsibleModule object
      results -- dict of return values for the calling code's module
      pkg_mgr -- some instance of a PkgMgr subclass

    In addition, "fn" may take other arbitrary KEYWORD arguments.

    Unfortunate caveats (for proper integration with existing code):

      The "module" object must contain at least two key-value pairs in
      its dict "params": "manager" and "strategy". For details, see the
      docs for Ansible's built-in "package_facts" module.

      "fn" should NOT call the module's "exit_json" method, lest
      execution end prematurely; also, prefer the "warn" method over
      "fail_json".

      When "fn" is decorated with this function, the calling code must
      omit argument "pkg_mgr" upon calling "fn".

    Arguments:
      fn -- callable that takes the arguments described above
    Errors:
      ValueError -- if erroneously called with argument "pkg_mgr"
    """

    @wraps(fn)
    def wrap_package_module(module, results, **kwargs):
        """Code abstracted from Ansible's package_facts module."""

        # Fail fast if called with "pkg_mgr".
        if "pkg_mgr" in kwargs:
            raise ValueError(
                'You should omit argument "pkg_mgr"'
                ' from this function call,'
                ' due to the decorator "for_each_pkg_mgr".'
            )

        # get supported pkg managers
        PKG_MANAGERS = get_all_pkg_managers()
        PKG_MANAGER_NAMES = [x.lower() for x in PKG_MANAGERS.keys()]

        managers = [x.lower() for x in module.params['manager']]
        strategy = module.params['strategy']

        if 'auto' in managers:
            # keep order from user, we do dedupe below
            managers.extend(PKG_MANAGER_NAMES)
            managers.remove('auto')

        unsupported = set(managers).difference(PKG_MANAGER_NAMES)
        if unsupported:
            if 'auto' in module.params['manager']:
                msg = 'Could not auto detect a usable package manager,' \
                    ' check warnings for details.'
            else:
                msg = 'Unsupported package managers requested: %s' \
                    % (', '.join(unsupported))
            module.fail_json(msg=msg)

        found = 0
        seen = set()
        for pkgmgr in managers:
            if found and strategy == 'first':
                break

            # dedupe as per above
            if pkgmgr in seen:
                continue
            seen.add(pkgmgr)

            try:
                try:
                    # manager throws exception on init (calls self.test)
                    # if not usable.
                    manager = PKG_MANAGERS[pkgmgr](module)
                    if manager.is_available():
                        found += 1
                        fn(module, results, pkg_mgr=manager, **kwargs)
                except Exception as e:
                    if pkgmgr in module.params['manager']:
                        module.warn('Requested package manager %s'
                                    ' was not usable by this module: %s'
                                    % (pkgmgr, to_text(e)))
                    continue
            except Exception as e:
                if pkgmgr in module.params['manager']:
                    module.warn('Function "%s" failed with package manager %s:'
                                ' %s' % (fn.__name__, pkgmgr, to_text(e)))

        if found == 0:
            msg = (
                'Could not detect a supported package manager'
                ' from the following list: %s,'
                ' or the required Python library is not installed.'
                ' Check warnings for details.'
                % managers
            )
            module.fail_json(msg=msg)

        module.exit_json(**results)

    return wrap_package_module
