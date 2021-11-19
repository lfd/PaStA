#!/usr/bin/bash

# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

project=$(cat config)
tags=$(git -C resources/$project/repo tag --list)
repo="./resources/$project/repo"

if [[ $project == "linux" ]]; then
	tags=$(git -C $repo tag --list | grep -v "^v2\.6\.")
elif [[ $project == "u-boot" ]]; then
	tags=$(git -C $repo tag --list | grep "^v20[12]" | grep -v "^v201[0123]" | grep -v "^v2014\.0[147]" | grep -v "v2014\.10-rc1")
elif [[ $project == "xen" ]]; then
	tags=$(git -C $repo tag --list | grep -v "^3" | grep -v "^\(RELEASE-\)\?4\.0\." | grep -v "RELEASE-[23]" | grep -P "^\d|R")
elif [[ $project == "qemu" ]]; then
	tags=$(git -C $repo tag --list | grep -v "^release" | grep -v "^v0\.[123456789]\." | grep -v "^v0\.1[0123]\." | grep -v "initial")
fi

RES="resources/$project/resources"
CLSTRS="$RES/maintainers_cluster"
SCTN="$RES/maintainers_section_graph"

mkdir -p $CLSTRS

for tag in $tags; do
	if [ -f $CLSTRS/$tag.txt ] && [ -f $SCTN/$tag.csv ] && [ -f $SCTN/${tag}_filemap.csv ]; then
		echo "Skipping $tag: already existing"
		continue
	fi
	./pasta maintainers_stats --mode graph --revision $tag
done
