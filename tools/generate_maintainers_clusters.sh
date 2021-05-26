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

RES="resources/$project/resources"
CLSTRS=$RES/maintainers_cluster

mkdir -p $CLSTRS

for tag in $tags; do
	if [ -f $CLSTRS/$tag.txt ]; then
		echo "Skipping $tag: already existing"
		continue
	fi
	./pasta maintainers_stats --mode graph --revision $tag
	mv $RES/maintainers_clusters.txt $CLSTRS/${tag}.txt
done
