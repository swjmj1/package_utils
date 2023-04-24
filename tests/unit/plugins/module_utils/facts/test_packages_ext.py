# SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible_collections.swjmj1.package_utils.plugins.module_utils.facts.packages_ext import PkgMgr


class PkgMgrExample(PkgMgr):
    def __init__(self, pkgs_in_repo, pkgs_installed):
        """Mock a package manager with a pretend repo.

        Arguments:
          pkgs_in_repo -- list of package names in the "repo"
          pkgs_installed -- (arbitrary) list of "installed" packages
        """

        self._repo = pkgs_in_repo
        self._installed = pkgs_installed

    def is_available(self):
        return True

    def list_installed(self):
        return self._installed

    def get_package_details(self, package):
        return {"name": package, "version": "1.0.0"}

    def search_pkg_substr(self, substr):
        return [pkg for pkg in self._repo if substr in pkg]


class TestPkgMgr():
    pkg_mgr = PkgMgrExample(
        [
            "pkg1-1", "pkg1-2", "pkg1-3",
            "pkg2-1", "pkg2-2", "pkg2-3",
            "pkg3-1", "pkg3-2", "pkg3-3",
        ],
        pkgs_installed=[]
    )

    def test_search_packages(self):
        """Ensure correctness of typical package name searches.

        Allow returned package details to contain extra info as long as
        they have the required keys "name" and "version".
        """

        search_results = self.pkg_mgr.search_packages("pkg1", "pkg2")
        expected = {
            "pkg1": [
                {"name": "pkg1-1", "version": "1.0.0"},
                {"name": "pkg1-2", "version": "1.0.0"},
                {"name": "pkg1-3", "version": "1.0.0"},
            ],
            "pkg2": [
                {"name": "pkg2-1", "version": "1.0.0"},
                {"name": "pkg2-2", "version": "1.0.0"},
                {"name": "pkg2-3", "version": "1.0.0"},
            ],
        }

        # Before anything else, ensure the results are indexed by the
        # given search terms. (Not worth doing a whole other test for.)
        assert len(search_results) == 2 \
            and search_results.get("pkg1") \
            and search_results.get("pkg2")

        # Ensure each received result *contains* the expected result.
        for pkg in ("pkg1", "pkg2"):
            for expected_result, received_result in zip(expected.get(pkg), search_results.get(pkg)):
                assert expected_result.items() <= received_result.items()
