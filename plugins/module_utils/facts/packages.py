# SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
# SPDX-License-Identifier: BSD-2-Clause


# This module file uses code from the following files in the official
# Ansible repo:
# * <https://github.com/ansible/ansible/raw/devel/lib/ansible/module_utils/facts/packages.py>
#
# The original copyright notice is as follows:

# (c) 2018, Ansible Project
# Simplified BSD License (see licenses/simplified_bsd.txt or https://opensource.org/licenses/BSD-2-Clause)


from __future__ import absolute_import, division, print_function
__metaclass__ = type

from abc import ABCMeta, abstractmethod

from ansible.module_utils.six import with_metaclass
from ansible.module_utils.common.process import get_bin_path
from ansible.module_utils.common._utils import get_all_subclasses


def get_all_pkg_managers():

    return {obj.__name__.lower(): obj for obj in get_all_subclasses(PkgMgr) if obj not in (CLIMgr, LibMgr)}


class PkgMgr(with_metaclass(ABCMeta, object)):  # type: ignore[misc]

    requires_module = False     # override as needed

    def __init__(self, module=None):
        """Store an AnsibleModule object, if given (as "module").

        If "module" is not given but is required, raise a ValueError. If
        "module" is given, store it as an attribute even if not
        required.
        """

        if module is None and self.requires_module:
            raise ValueError("This PkgMgr needs an AnsibleModule object.")
        self.module = module

    @abstractmethod
    def is_available(self):
        """
        This method is supposed to return True/False if the package
        manager is currently installed/usable It can also 'prep' the
        required systems in the process of detecting availability

        The calling code's AnsibleModule object may have to be given as
        an argument, depending on the subclass. A ValueError should be
        raised if it is needed but not given.
        """
        pass

    @abstractmethod
    def list_installed(self):
        """
        This method should return a list of installed packages, each
        list item will be passed to get_package_details

        The calling code's AnsibleModule object may have to be given as
        an argument, depending on the subclass. A ValueError should be
        raised if it is needed but not given.
        """
        pass

    @abstractmethod
    def get_package_details(self, package):
        """
        This takes a 'package' item and returns a dictionary with the
        package information, name and version are minimal requirements
        """
        pass

    @abstractmethod
    def search_pkg_substr(self, substr):
        """
        Search for packages, installed or not, whose names in the
        machine's local repository indices match the given substring.
        """
        pass

    def get_packages(self):
        """
        Take all of the above and return a dictionary of lists of
        dictionaries (package = list of installed versions)
        """

        installed_packages = {}
        for package in self.list_installed():
            package_details = self.get_package_details(package)
            if 'source' not in package_details:
                package_details['source'] = self.__class__.__name__.lower()
            name = package_details['name']
            if name not in installed_packages:
                installed_packages[name] = [package_details]
            else:
                installed_packages[name].append(package_details)
        return installed_packages

    def search_packages(self, *search_terms):
        """Search all local repo indices by the given search terms.

        Return a dictionary where each key is a given search term, each
        of whose values is a list of dictionaries returned by the
        "get_package_details" method in this class. (I.e., return a
        dictionary of lists of dictionaries.)

        For each search term with no matches found, the corresponding
        value is an empty list. If no search terms are given, then the
        whole returned dictionary is empty.

        Since some package managers can return "matches" whose names do
        not match the given search term -- e.g., apk returns "john" when
        searching for "ansible" -- any spurious results are pruned from
        the return value.

        Arguments:
          *search_terms -- sequence of strings to match against local
                           repo indices (with any duplicate items
                           automatically removed upon processing)
        """

        search_results = {}
        for substr in set(search_terms):
            result_list = []
            for package in self.search_pkg_substr(substr):
                package_details = self.get_package_details(package)
                if 'source' not in package_details:
                    package_details['source'] = self.__class__.__name__.lower()
                if substr in package_details['name']:
                    result_list.append(package_details)
            search_results[substr] = result_list
        return search_results


class LibMgr(PkgMgr):

    LIB = None  # type: str | None

    def __init__(self, module=None):

        self._lib = None
        super(LibMgr, self).__init__(module)

    def is_available(self):
        found = False
        try:
            self._lib = __import__(self.LIB)
            found = True
        except ImportError:
            pass
        return found


class CLIMgr(PkgMgr):

    requires_module = True      # must have access to method run_command
    CLI = None  # type: str | None

    def __init__(self, module=None):

        self._cli = None
        super(CLIMgr, self).__init__(module)

    def is_available(self):
        try:
            self._cli = get_bin_path(self.CLI)
        except ValueError:
            return False
        return True
