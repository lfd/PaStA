#!/bin/bash

# Copyright (c) OTH Regensburg, 2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

GIT="git -C ${1} --no-pager"
LISTNAME=$2
BASEDIR=$3
HASH=$4

$GIT show $HASH:m | ./process_mail_pipe.sh $LISTNAME $BASEDIR $TMP
exit $?
