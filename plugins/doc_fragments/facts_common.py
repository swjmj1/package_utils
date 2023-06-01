# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
    options:
      manager:
        description:
          - The package manager used by the system so we can query the
            package information.
          - Since 2.8 this is a list and can support multiple package
            managers per system.
          - The 'portage' and 'pkg' options were added in version 2.8.
          - The 'apk' option was added in version 2.11.
          - The 'pkg_info' option was added in version 2.13.
        default: ['auto']
        choices: ['auto', 'rpm', 'apt', 'portage', 'pkg', 'pacman', 'apk', 'pkg_info']
        type: list
        elements: str
      strategy:
        description:
          - This option controls how the module queries the package
            managers on the system.
          - C(first) means it will return only information for the first
            supported package manager available.
          - C(all) will return information for all supported and
            available package managers on the system.
        choices: ['first', 'all']
        default: 'first'
        type: str
    requirements:
        - For 'portage' support it requires the C(qlist) utility, which
          is part of 'app-portage/portage-utils'.
        - For Debian-based systems C(python-apt) package must be
          installed on targeted hosts.
        - For SUSE-based systems C(python3-rpm) package must be
          installed on targeted hosts. This package is required because
          SUSE does not include RPM Python bindings by default.
    attributes:
        check_mode:
            support: full
        diff_mode:
            support: none
        facts:
            support: full
        platform:
            platforms: posix
    """
