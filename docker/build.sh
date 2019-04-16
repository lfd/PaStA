#!/bin/bash
#
# Copyright (c) OTH Regensburg, 2017-2019
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

type=$1

function build_container() {
	tag=$1
	docker build --tag pasta:$tag -f pasta-${tag}.dockerfile .
}

# In any case, we need to build the base container
build_container base

case $type in
"base")
	exit 0
	;;
"linux")
	build_container $type
	;;
"icse-artifact")
	build_container linux
	build_container $type
	;;
*)
	echo "Unknown target $type"
	exit 1
	;;
esac

exit 0
