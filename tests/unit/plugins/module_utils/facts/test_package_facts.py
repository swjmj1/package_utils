# SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
# SPDX-License-Identifier: GPL-3.0-or-later


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible_collections.swjmj1.package_utils.plugins.module_utils.facts.packages import PkgMgr
from ansible_collections.swjmj1.package_utils.plugins.module_utils.facts.package_facts import for_each_pkg_mgr


class PkgMgrDummy(PkgMgr):
    def __init__(self, module=None):
        super(PkgMgrDummy, self).__init__()

    def is_available(self):
        return True

    def list_installed(self):
        return []

    def get_package_details(self, package):
        return {}

    def search_pkg_substr(self, substr):
        return []


# We want multiple dummy package managers in order to test the process
# of finding them (even if, say, one package manager is unavailable).
class PkgMgrDummyTwo(PkgMgrDummy):
    pass


class PkgMgrDummyThree(PkgMgrDummy):
    pass


class UnavailablePkgMgr(PkgMgrDummy):
    def is_available(self):
        return False


class MockAnsibleModule():
    """Mock AnsibleModule class.

    Real AnsibleModule objects don't play nicely with pytest.

    We just need a few methods for the tests to work. It doesn't matter
    what they do besides keep track of the arguments given to them.
    """

    def __init__(self, strategy, *managers):
        self.params = {
            "strategy": strategy,
            "manager": managers,
        }
        self.warnings = []
        self.fail_msg = None
        self.results = {}

    def warn(self, msg):
        self.warnings.append(msg)

    def fail_json(self, msg):
        self.fail_msg = msg

    def exit_json(self, **kwargs):
        self.results = kwargs


@for_each_pkg_mgr
def module_fn(module, results, pkg_mgr):
    """Collect each package manager given to this function."""
    results["pkg_mgr_list"].append(pkg_mgr.__class__.__name__)


class TestModuleWrapper():
    """Test the functionality added to Ansible's package_facts."""

    results = {"pkg_mgr_list": []}      # initial value of results

    def test_one_pkg_mgr_choosing_first(self):
        module = MockAnsibleModule("first", "PkgMgrDummy")
        module_fn(module, self.results)
        assert module.results["pkg_mgr_list"] == ["PkgMgrDummy"]

    def test_one_pkg_mgr_choosing_all(self):
        module = MockAnsibleModule("all", "PkgMgrDummy")
        module_fn(module, self.results)
        assert module.results["pkg_mgr_list"] == ["PkgMgrDummy"]

    def test_three_pkg_mgrs_choosing_first(self):
        """For strategy "first", use ONLY the first of three."""

        module = MockAnsibleModule(
            "first",
            "PkgMgrDummy", "PkgMgrDummyTwo", "PkgMgrDummyThree",
        )
        module_fn(module, self.results)
        assert module.results["pkg_mgr_list"] == ["PkgMgrDummy"]

    def test_three_pkg_mgrs_choosing_all(self):
        module = MockAnsibleModule(
            "all",
            "PkgMgrDummy", "PkgMgrDummyTwo", "PkgMgrDummyThree",
        )
        module_fn(module, self.results)
        assert module.results["pkg_mgr_list"] == [
            "PkgMgrDummy", "PkgMgrDummyTwo", "PkgMgrDummyThree",
        ]

    def test_unavailable_pkg_mgr_choosing_first(self):
        """Skip the unavailable package manager, then use the next."""

        module = MockAnsibleModule(
            "first",
            "UnavailablePkgMgr",
            "PkgMgrDummy", "PkgMgrDummyTwo", "PkgMgrDummyThree",
        )
        module_fn(module, self.results)
        assert module.results["pkg_mgr_list"] == ["PkgMgrDummy"]

    def test_unavailable_pkg_mgr_choosing_all(self):
        """Skip the unavailable package manager, then use the rest."""

        module = MockAnsibleModule(
            "all",
            "UnavailablePkgMgr",
            "PkgMgrDummy", "PkgMgrDummyTwo", "PkgMgrDummyThree",
        )
        module_fn(module, self.results)
        print(module.results)
        assert module.results["pkg_mgr_list"] == [
            "PkgMgrDummy", "PkgMgrDummyTwo", "PkgMgrDummyThree",
        ]

    def test_bad_fn_call(self):
        """Raise an Error if given argument "pkg_mgr".

        Ensure the error message at least mentions "pkg_mgr" by name (as
        a sanity check).
        """

        module = MockAnsibleModule("", [])
        pkg_mgr = PkgMgrDummy()
        try:
            module_fn(module, self.results, pkg_mgr=pkg_mgr)
            assert False
        except ValueError as e:
            assert "pkg_mgr" in str(e)
