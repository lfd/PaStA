#!/bin/bash

# Copyright (c) OTH Regensburg, 2017-2019
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@othr.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

. ./global.env

initialise

if [ "$#" -ne 4 ]; then
	echo "Usage: $0 listname destination_directory mailbox_file"
	echo
	echo "This script splits up a mailbox file into seperate mail"
	echo "files, placed into date-separated subdirectories."
	exit 1
fi

if [ -d ${VICTIM} ]; then
	find ${VICTIM} -type f -print0 | \
		xargs -0 -P $(nproc) -n 1 \
			./process_mail.sh $USE_PATCHWORK_ID $LISTNAME $BASEDIR
elif [ -f ${VICTIM} ]; then
	formail -n $(nproc) -s <${VICTIM} ./process_mail_pipe.sh $USE_PATCHWORK_ID $LISTNAME $BASEDIR
else
	echo "${VICTIM} is not a file or directory"
	exit 1
fi

if [ $? -ne 0 ]; then
	exit 1
fi

sort_lists
