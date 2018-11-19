#!/bin/bash

# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
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

function parse_date {
	local DATE=$1

	if [ "$DATE" == "" ]; then
		return 1
	fi

	local YEAR=$(date -d "${DATE}" "+%Y" 2> /dev/null)
	if [ $? -ne 0 ]; then
		return 1
	fi

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

ID=$(formail -x "Message-id" -c < $MAIL | tail -n 1 | sed -e 's/.*\(<.*>\).*/\1/i')
whitespace_pattern=" |'"
if [ "$ID" = "" ]; then
	die "Unable to parse Message ID for ${MAIL}: empty Message-ID"
elif [[ "$ID" =~ $whitespace_pattern ]]; then
	die "Uable to parse Message ID for ${MAIL}: contains whitespaces"
fi

MD5=$(echo -en $ID | md5sum | awk '{ print $1 }')

# Try to get a valid mail date
DATE_HDR=$(formail -x Date < $MAIL | tail -n 1)
DATE=$(parse_date "$DATE_HDR")
if [ "$DATE" == "" ]; then
	DATE_HDR=$(echo $DATE_HDR | sed -e 's/\(.*\)\s\(.*\)\.\(.*\)\.\(.*\)\s\(.*\)/\1 \2:\3:\4 \5/g')
	DATE=$(parse_date "$DATE_HDR")
fi
if [ "$DATE" == "" ]; then
	DATE_HDR=$(formail -x NNTP-Posting-Date < $MAIL | tail -n 1)
	DATE=$(parse_date "$DATE_HDR")
fi
# last chance, try to used the Received field
if [ "$DATE" == "" ]; then
	DATE_HDR=$(formail -x Received -c < $MAIL | tail -n 1 | sed -e 's/.*;\s*\(.*\)/\1/')
	DATE=$(parse_date "$DATE_HDR")
fi
if [ "$DATE" == "" ]; then
	die "Nope, I'm sorry. No way to parse this mail: $MAIL"
fi

# no lock required, echo will write atomatically when writing short lines
echo "$ID $LISTNAME" >> ${LISTS}

DSTDIR="${BASEDIR}/${DATE}"
DSTFILE="${DSTDIR}/${MD5}"
[ -d $DSTDIR ] || mkdir -p $DSTDIR

# check if the mail itself already exists
if [ ! -f $DSTFILE ]; then
	cp $MAIL $DSTFILE
fi

# check if the mail is already indexed
if ! grep -q "${MD5}" ${INDEX} ${INVALID}; then
       echo "$DATE $ID $MD5" >> ${INDEX}
fi
