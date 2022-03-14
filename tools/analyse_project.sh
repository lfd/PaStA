#!/bin/bash

# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

set -e

project=$1

RES="./resources/$project/resources/"
RESULT="$HOME/results/$project/"

analyse () {
	./pasta analyse $1 -tf 1 -th 1 -adi 365
	./pasta rate -ta 0.8 -ti 0.8
	./pasta rate -w 1 -ta 1 -ti 1
	./pasta rate -w 0 -ta 1 -ti 1
}

./pasta set_config $project

if [ $project == "linux" ]; then
	./analyses/ignored_patches.R $RES/R $RES/characteristics.csv $RES/releases.csv
else
	# Remove invalids, we have to update to latest&greatest resources, so we have
	# to rebuild it in any case.
	rm -fv $RES/mbox/invalid/*

	# We must do that under all circumstances, as the upstream repo might have new
	# versions that we don't yet track.
	./tools/generate_maintainers_clusters.sh
	./pasta sync -mbox -create all

	analyse rep
	analyse upstream

	./pasta prepare_evaluation --process_characteristics
fi


# Remove pkl files to save memory
rm -fv $RES/*.pkl

# Compile tex files
cd $RES/R
for i in */; do
	cd $i
	mkdir build
	for j in *_standalone.tex; do
		pdflatex -interaction=nonstopmode -output-directory=build/ $j
		mv -v build/${j%.*}.pdf .
	done
	rm -rf build
	cd ..
done

mkdir -p $RESULT
cp -av * $RESULT

cd $HOME/PaStA
./fse22-artifact/meiomei.sh
