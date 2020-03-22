#!/bin/bash

# Copyright (c) OTH Regensburg, 2019
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.


PROJECT=$(cat config)
PASTA=./pasta
RES=resources/$PROJECT

function update_repo {
	git -C $1 checkout master
	git -C $1 fetch --all
	git -C $1 merge
	git -C $1 gc --auto

	git add $1
}

pushd $RES

# Update upstream
update_repo repo/

pushd resources/mbox/pubin

# Don't use git submodule foreach, we only want to affect the current project
for inbox in */*/*.git; do
	update_repo $inbox

done

popd # Project root

popd # Pwd

$PASTA sync -mbox -create downstream

pushd $RES

git add resources/mbox/index/pubin/
git add resources/stack-hashes/upstream
git add resources/mbox/invalid/

git commit -m "${PROJECT}: forward upstream"

popd # Pwd
