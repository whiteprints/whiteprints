#!/usr/bin/env python

# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level executable."""

import sys

from whiteprints.cli.cli_entrypoint import entrypoint


sys.exit(entrypoint())
