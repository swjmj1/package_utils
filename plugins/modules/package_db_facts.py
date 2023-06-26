#!/usr/bin/python
# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
# SPDX-License-Identifier: GPL-3.0-or-later

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = """
module: package_db_facts
short_description: Facts about search results for package names
description:
    - Given a list of package name substrings as search terms, return
      information about each matching package from the system's local
      package database. Here, "package database" refers to wherever the
      system's package manager keeps metadata about its package
      repositories.
    - The returned packages themselves may or may not be installed on
      the system in question; to find out which packages are installed,
      cross-reference results with the M(ansible.builtin.package_facts)
      module.
    - A package matches a given search term if it contains that term as
      a substring.
    - Note that no connection to online repositories is made by this
      module, because only the package manager's local database is
      queried. It is up to the invoking role or playbook to ensure the
      package database is up to date (if desired).
    - When it comes to support, the goal of this module is to support
      any package manager supported by the
      M(ansible.builtin.package_facts) module.
author: swjmj1 @swjmj1
options:
    search_terms:
        description:
            - A list of substrings to search for in the system's local
              package database.
        required: true
        type: list
        elements: str
seealso:
    - module: ansible.builtin.package_facts
      description: >
          The original, built-in package facts module on which this is
          based.
extends_documentation_fragment:
    - action_common_attributes
    - action_common_attributes.facts
    - swjmj1.package_utils.facts_common
"""


EXAMPLES = """
- name: Search for packages whose names contain "python" and "ansible"
  swjmj1.package_utils.package_db_facts:
    search_terms: ["python", "ansible"]

- name: Print the search results
  ansible.builtin.debug:
    var: ansible_facts.package_search_results
"""


# Largely copied from Ansible's package_facts.py.
RETURNS = """
ansible_facts:
  description: Facts to add to ansible_facts.
  returned: always
  type: complex
  contains:
    package_search_results:
      description:
        - A dict mapping each given search term to a list of matching
          packages, where each matching package is represented by a dict
          of package details (see below).
        - Every dict in the list corresponds to one version of the
          package that was found in the local package database.
        - The fields described below are present for all package
          managers. Depending on the package manager, there might be
          more fields for a package.
      returned: >
        when operating system level package manager is specified or auto
        detected manager type: dict
      contains:
        name:
          description: The package's name.
          returned: always
          type: str
        version:
          description: The package's version.
          returned: always
          type: str
        source:
          description: Where information on the package came from.
          returned: always
          type: str
    sample: |
      {
        "package_search_results": {
          "ansible": [
            {
              "name": "ansible-core",
              "source": "apk",
              "version": "2.13.6-r0"
            },
            {
              "name": "ansible-lint",
              "source": "apk",
              "version": "6.9.1-r0"
            },
            ...
          ]
        }
      }
"""


from ansible.module_utils.basic import AnsibleModule

from ansible_collections.swjmj1.package_utils.plugins.module_utils.facts.packages \
    import get_all_pkg_managers
from ansible_collections.swjmj1.package_utils.plugins.module_utils.facts.package_facts \
    import for_each_pkg_mgr


@for_each_pkg_mgr
def main(module, results, pkg_mgr):
    """Use the given package manager to search for matching packages.

    If search_terms is empty, then no new results are added.
    """

    search_results = pkg_mgr.search_packages(*module.params["search_terms"])
    results["ansible_facts"]["package_search_results"].update(search_results)


if __name__ == "__main__":
    module = AnsibleModule(
        argument_spec={
            "manager": {
                'type': 'list',
                'elements': 'str',
                'choices': ['auto'] + list(get_all_pkg_managers().keys()),
                'default': ['auto'],
            },
            "strategy": {
                'choices': ['first', 'all'],
                'default': 'first',
            },
            "search_terms": {
                'type': 'list',
                'elements': 'str',
                'required': True,
            },
        },
        supports_check_mode=True
    )
    results = {
        "ansible_facts": {"package_search_results": {}}
    }
    main(module, results)
