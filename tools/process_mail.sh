#!/bin/bash

# Copyright (c) OTH Regensburg, 2017
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@othr.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

# Sorts one single mail. Invoked by process_mailbox.sh

LISTNAME=$1
BASEDIR=$2
MAIL=$3

LISTS=${BASEDIR}/lists
INVALID=${BASEDIR}/invalid
INDEX=${BASEDIR}/index

function die {
	echo "$@" 1>&2
	exit 1
}

function get_date {
	local HEADER=$1
	local DATE=$(cat $MAIL | grep "^${HEADER}:" | head -n 1 |
		     sed -e "s/${HEADER}:\s*//")
	local YEAR=$(date -d "${DATE}" "+%Y")

	if [ "$YEAR" == "" ]; then
		return 1
	fi

	if [ "$YEAR" -lt "1970" ]; then
		return 2
	fi

	local MD=$(date -d "${DATE}" "+%m/%d")

	echo "${YEAR}/${MD}"
	return 0
}

ID=$(cat -v $MAIL | grep -i "^Message-ID:" | head -n 1 |
     sed -e 's/Message-ID:\s*\(.*\)/\1/i' -e 's/\s*$//')
if [ "$ID" = "" ]
then
	die "Unable to parse Message ID for $MAIL"
fi
MD5=$(echo -en $ID | md5sum | awk '{ print $1 }')

# Try to get a valid mail date
DATE=$(get_date Date)
R=$?
if (($R > 0)); then
	echo "Invalid Date (Error: $R, ID: $ID)"
	echo "Fall back to NNTP date..."
	DATE=$(get_date NNTP-Posting-Date)
	if (($? > 0)); then
		die "Nope, I'm sorry. No way to parse this mail."
	fi
	echo "Success."
fi

echo "$ID $LISTNAME" >> ${LISTS}

DSTDIR="${BASEDIR}/${DATE}"
DSTFILE="${DSTDIR}/${MD5}"
[ -d $DSTDIR ] || mkdir -p $DSTDIR

if [ ! -f $DSTFILE ]; then
	cp $MAIL $DSTFILE
fi

# no lock required, echo will write atomatically when writing short lines
echo "$DATE $ID $MD5" >> ${INDEX}
