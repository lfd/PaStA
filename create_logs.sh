#!/bin/bash

source common.sh

FORMATSTR="%s%n%b"

AFFECTED_FILES_DIR="$LOGDIR/affected_files"
AUTHOR_DATES_DIR="$LOGDIR/author_dates"
AUTHOR_EMAILS="$LOGDIR/author_emails"
DIFF_DIR="$LOGDIR/diffs"
MESSAGES_DIR="$LOGDIR/messages"

NPROC=$(nproc)

mkdir -p $AFFECTED_FILES_DIR $AUTHOR_DATES_DIR $AUTHOR_EMAILS $DIFF_DIR $MESSAGES_DIR

function create_log {
	version_range=$1
	format_string=$2
	additional_argument=$3
	location=$4

	git -C $KERNELDST --no-pager log --pretty=format:%H $version_range | \
		xargs -n 1 -P $NPROC -I {} \
			sh -c 'git -C $1 --no-pager show $2 --pretty=format:$3 $4 > $5/$4' \
				-- "$KERNELDST" "$additional_argument" "$format_string" "{}" "$location"
}

function create_log_for_version_range {
	version_range=$1

	echo "Creating message log for ${version_range}..."
	create_log "$version_range" "%s%n%b" "--quiet" $MESSAGES_DIR

	echo "Creating affected files log for ${version_range}..."
	create_log "$version_range" "" "--name-only" $AFFECTED_FILES_DIR

	echo "Creating diff log for ${version_range}..."
	create_log "$version_range" "" "--patience" $DIFF_DIR

	echo "Creating author date log for ${version_range}..."
	create_log "$version_range" "%at" "--quiet" $AUTHOR_DATES_DIR

	echo "Creating author email log for ${version_range}..."
	create_log "$version_range" "%ae" "--quiet" $AUTHOR_EMAILS
}

# From master down to Genesis
create_log_for_version_range ""

# Traverse through every single branch
branches=$(git -C $KERNELDST branch -l | grep analysis)
for i in $branches
do
	echo working on $i
	rtversion=$(echo $i | sed -e 's/analysis-//')
	baseversion=$(echo $rtversion | sed -e 's/-rt.*//')

	if [ "$baseversion" = "3.12.0" ] || [ "$baseversion" = "3.14.0" ]; then
		baseversion=$(sed -e 's/\.0$//' <<< $baseversion)
    fi

	create_log_for_version_range "v${baseversion}..${i}"
done
