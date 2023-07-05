<!--
SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
SPDX-License-Identifier: CC0-1.0
-->


# Ansible Collection - swjmj1.package_utils

An Ansible collection adding extra ways to interact with package
managers (portably)

[![builds.sr.ht status](https://builds.sr.ht/~swjmj1/package_utils/commits/main.svg)](https://builds.sr.ht/~swjmj1/package_utils/commits/main?)

package_utils extends Ansible's functionality for interacting with
package managers. It aims to provide new modules or roles that invoke a
target system's package manager for use cases not covered by Ansible's
built-in modules. With each feature, the goal here is to unify
functionality across package managers into one interface, enabling roles
and playbooks to do package management portably—such that it behaves
similarly for any package manager that Ansible supports out of the box,
namely:

* apk
* APT
* Pacman
* pkg
* pkg_info
* Portage
* RPM

If you've ever had to clumsily, non-portably use `shell` for a random
use case involving package management, then maybe your use case is
better covered here. Or maybe not.


## Status

This is in early development. Expect few features for now. This won't be
on Ansible Galaxy until it hits v1.0.0, which will happen once it's
useful enough.

Support for most of the package managers listed above is still in
progress. Read the blurb for each module or role to see which package
managers are working.


## Features

### Modules
* `package_db_facts` — Search the package manager's local database for a
  list of given search terms.
    * Currently, apk and Pacman are tested and working. Support for pkg,
      pkg_info, and APT is in progress. Meanwhile, RPM support is
      complicated by the fact that it can only search *installed*
      packages. For Portage, Gentoo needs to be working in Sourcehut's
      CI.

### Roles
* `pkg_name_prompt` — For a given package name, interactively display
  search results from the target system's package database so that
  differences in package names across distros can be resolved lazily.
    * Not yet implemented. Waiting on `package_db_facts`.
