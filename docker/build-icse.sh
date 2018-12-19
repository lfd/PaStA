#!/bin/bash
#
# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.


# build pasta base image
./build.sh

# build icse artifact image
docker build --tag pasta:icse-artifact -f pasta-icse-artifact.dockerfile .
