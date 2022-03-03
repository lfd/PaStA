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
revision=$2

# !FIXME Add argument sanity checks

RESOURCES="./resources/$project/resources"
TEX_IMG_DST="$RESOURCES/maintainers_cluster_img/$revision/"
VERTEX_NAMES="$RESOURCES/maintainers_cluster/$revision.txt"
PDF_DST="$TEX_IMG_DST/build"
REPRO="./fse22-artifact/cluster_gui/$project-$revision/"
SOLUTION="$REPRO/solution.csv"

./pasta set_config $project

# 1. Create the tex files
./analyses/maintainers_section_graph.R \
	$TEX_IMG_DST \
	"$RESOURCES/maintainers_section_graph/$revision.csv" \
	"$RESOURCES/maintainers_section_graph/${revision}_filemap.csv" \
	--print-clusters

# 2. Randomise clusters
./fse22-artifact/randomise_cluster.py \
	$VERTEX_NAMES \
	$TEX_IMG_DST

# 3. Latex: compile all clusters
mkdir -p $TEX_IMG_DST/build
for i in $TEX_IMG_DST/*_standalone.tex; do
	pdflatex -interaction=nonstopmode -output-directory=$PDF_DST $i
done

# 4. Move PDFs
mv -v $PDF_DST/*.pdf $TEX_IMG_DST
rm -rf $PDF_DST

# 5. Convert all PDFs to PNGs
for i in $TEX_IMG_DST/*.pdf; do
	pdftoppm -png -singlefile $i ${i%.*}
done

# 6. Copy the PNGs to the destination directory
mkdir -p $REPRO
for cluster in $TEX_IMG_DST/*.png; do
	cp -v $cluster $REPRO
done

# 7. Determine a random solution for the project
echo -en > $SOLUTION
for cluster in $REPRO/cluster_*.png; do
	location=$(echo $(($RANDOM % 2)) | sed 's/0/l/' | sed 's/1/r/')
	echo "$(basename $cluster), $location" >> $SOLUTION
done
