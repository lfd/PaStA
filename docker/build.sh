#!/bin/bash
#
# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

docker build --tag pasta -f pasta-base.dockerfile .
