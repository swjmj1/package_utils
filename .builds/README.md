<!--
SPDX-FileCopyrightText: 2023 swjmj1 <swjmj1@tuta.io>
SPDX-License-Identifier: CC0-1.0
-->


# Sourcehut build manifests

Whenever this repo is pushed to its [Sourcehut remote][1], up to four
build manifests in this directory are submitted for testing. (Any more
and four are selected randomly, which is how Sourcehut works.)

Each manifest here tests a specific package manager by using an
appropriate build image. Basic tests for REUSE compliance and approval
from `ansible-lint` are in `pacman.yml` (mainly because running an
up-to-date `ansible-lint` is easiest on Arch Linux). If, on a given push
to Sourcehut, the basic tests in `pacman.yml` are not selected for
submission, then `pacman.yml` can just be submitted manually via
Sourcehut's web interface.

[1]: https://git.sr.ht/~swjmj1/package_utils
