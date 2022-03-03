# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:linux

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

## 1. Prepare resources
# Take linux/2011 as base
WORKDIR /home/pasta/PaStA/resources

# FIXME! Pin this to a git tag
RUN git checkout linux/2011

## 2. Initialise submodules
RUN git submodule init
# repositories: only for our target projects
RUN git submodule update u-boot/repo qemu/repo linux/repo xen/repo
# Mailing lists: only for our targets, except Linux
# u-boot
RUN git submodule update u-boot/resources/mbox/pubin/lists.denx.de/u-boot/0.git
# xen (symlinked)
RUN git submodule update linux/resources/mbox/pubin/lists.xenproject.org
# qemu (symlinked)
RUN git submodule update linux/resources/mbox/pubin/nongnu.org

# Switch to latest & greatest resources
RUN git submodule foreach git reset --hard origin/master
