#!/bin/bash

# Copyright (c) OTH Regensburg, 2017-2020
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

# Sorts one single mail. Invoked by process_mailbox.sh

. ./global.env

MAIL=$VICTIM

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

whitespace_pattern=" |'"

function get_header {
	# Also remove preceeding and trailing whitespaces from the header
	formail -x $1 -c < $MAIL | head -n 1 | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

if [ "$ARCHIVE_TYPE" = "patchwork" ]; then
	PATCHWORK_ID=$(get_header "X-Patchwork-ID")

	if [ "$PATCHWORK_ID" = "" ]; then
		echo "Unable to parse Patchwork ID for ${MAIL}: empty Patchwork ID"
		exit 0
	fi
	# Always surround emails by <> tags. PaStA needs them in order to
	# classify them as emails
	PATCHWORK_ID=" ${PATCHWORK_ID}"
fi

ID=$(get_header "Message-id" | sed -e 's/.*\(<.*>\).*/\1/i')
if [ "$ID" = "" ]; then
	echo "Unable to parse Message ID for ${MAIL}: empty Message-ID"
	exit 0
elif [[ "$ID" =~ $whitespace_pattern ]]; then
	echo "Unable to parse Message ID for ${MAIL}: contains whitespaces"
	exit 0
elif ! [[ "$ID" =~ \<.*\> ]]; then
	echo "Unable to parse Message ID for ${MAIL}: Invalid Message-ID format: ${ID}"
	exit 0
fi

MD5=$(md5sum $MAIL | awk '{ print $1 }')

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
	echo "Nope, I'm sorry. No way to parse this mail: $MAIL"
	exit 0
fi

DSTDIR="${BASEDIR}/${ARCHIVE_TYPE}/${DATE}"
DSTFILE="${DSTDIR}/${MD5}"
[ -d $DSTDIR ] || mkdir -p $DSTDIR

# check if the mail itself already exists
if [ ! -f $DSTFILE ]; then
	cp $MAIL $DSTFILE
fi

# no lock required, echo will write atomatically when writing short lines
echo "$DATE $ID ${MD5}${PATCHWORK_ID}" >> ${INDEX}
