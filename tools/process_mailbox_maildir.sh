#!/bin/bash

# Copyright (c) OTH Regensburg, 2017
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@othr.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

function die {
	echo "$@" 1>&2
	exit -1;
}

if [ "$#" -ne 3 ]; then
	echo "Usage: $0 listname mailbox_file destination_directory"
	echo
	echo "This script splits up a mailbox file into seperate mail"
	echo "files, placed into date-separated subdirectories."
	exit 1
fi

LISTNAME=${1}
VICTIM=${2}
BASEDIR=${3}
LISTS=${BASEDIR}/lists
INDEX=${BASEDIR}/index

mkdir -p $BASEDIR || die "Unable to create basedir"

if [ -d ${VICTIM} ]; then
	find ${VICTIM} -type f -print0 | \
		xargs -0 -P $(nproc) -n 1 \
			./process_mail.sh ${LISTNAME} ${BASEDIR}
elif [ -f ${VICTIM} ]; then
	formail -n $(nproc) -s <${VICTIM} ./process_mail_pipe.sh ${LISTNAME} ${BASEDIR}
else
	echo "${VICTIM} is not a file or directory"
	exit 1
fi

if [ $? -ne 0 ]; then
	exit 1
fi

sort -u $LISTS -o $LISTS
sort -u $INDEX -o $INDEX
