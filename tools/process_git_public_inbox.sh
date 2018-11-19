#!/bin/bash

# Copyright (c) OTH Regensburg, 2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

. ./global.env

GIT="git -C ${VICTIM} --no-pager"
REPO_NAME=$(basename ${VICTIM})
STATE=${BASEDIR}/${REPO_NAME}.state

# Try to update the mailbox
$GIT checkout master
$GIT pull

if [ -f $STATE ]; then
	INITIAL=$(cat ${STATE})
	LIST=$($GIT rev-list --all ${INITIAL}..)
	if [ -z "$LIST" ]; then
		echo "Everything is up to date, nothing to be done"
		exit 0
	fi
else
	LIST=$($GIT rev-list --all)
	INITIAL=$(tail -n 1 <<< ${LIST})
fi

HEAD=$(head -n 1 <<< ${LIST})

echo "Initial commit: $INITIAL"
echo "Current head: $HEAD"

echo $LIST | xargs -P $(nproc) -n 1 ./process_mail_git.sh ${VICTIM} ${LISTNAME} ${BASEDIR}

echo $HEAD > $STATE

sort_lists
