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
build_container skeleton

# build intermediate targets
case $type in
"skeleton")
	exit 0
	;;
"base")
	;;
"linux")
	build_container base
	;;
"saner22-stage1")
	build_container base
	build_container linux
	;;
"saner22-stage2")
	build_container base
	build_container linux
	build_container saner22-stage1
	;;
"saner22-stage3")
	build_container base
	build_container linux
	build_container saner22-stage1
	build_container saner22-stage2
	;;
"icse-artifact")
	build_container base
	build_container linux
	;;
*)
	echo "Unknown target $type"
	exit 1
	;;
esac

# build the final target
build_container $type

exit 0
