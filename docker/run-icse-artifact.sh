#!/bin/bash
#
# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

IMAGE="https://cdn.lfdr.de/PaStA/docker-pasta-icse.tar.gz"

# check if image is already present
docker inspect --type=image pasta:icse-artifact > /dev/null 2>&1

# if not, download the image
if [ $? -ne 0 ]; then
	curl $IMAGE  | zcat -d | docker load
fi

docker run pasta:icse-artifact ./icse-artifact-analysis.sh
