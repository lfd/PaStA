# Copyright (c) OTH Regensburg, 2017-2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:base

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

RUN git -C resources/ submodule update linux/repo
