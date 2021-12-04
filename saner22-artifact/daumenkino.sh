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

daumenkino="$HOME/results/daumenkino/$project"
template="./saner22-artifact/tikz_template.tex"
build="$daumenkino/build"

mkdir -p $daumenkino $build

./pasta set_config $project

realpath ./resources/$project/resources/maintainers_section_graph/* | grep -v -- "-rc" | grep -v "filemap" | \
	xargs -n 1 -I {} -P $(nproc) bash -c "./analyses/tex_generator.R {} \$(echo {} | sed -e 's/\.csv/_filemap\.csv/')"

for i in resources/$project/resources/R/graphdesc*.tex; do
	./saner22-artifact/daumenkino/daumenkino.py -i $i -o $daumenkino/$(basename $i)
done

ls $daumenkino/*.tex | \
	xargs -n 1 -I {} -P $(nproc) \
	bash -c "lualatex -output-directory $build -jobname \$(basename -s .tex {}) \"\\newcommand{\\version}{\$(basename -s .tex {} | cut -b 11-)}\\newcommand{\\filename}{{}}\\input{$template}\""

mv -v $build/*.pdf $daumenkino/

files=$(ls $daumenkino/*.pdf | sort -V)
pdftk $files cat output $daumenkino/daumenkino.pdf
