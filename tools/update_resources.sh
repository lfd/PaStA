#!/bin/bash

# Copyright (c) OTH Regensburg, 2020
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

set -e

old_lkml_pubin="resources/linux/resources/mbox/pubin/vger.kernel.org/linux-kernel/"

# Update resources to the current version
git submodule update --init resources

# Initialise repositories
git -C resources submodule init

# upstream url might have changed, keep them in sync
git -C resources submodule sync

# forward repositories
git -C resources submodule update

# remove "old" lkml directory, if existent
[ -d $old_lkml_pubin ] && rm -rfv $old_lkml_pubin
