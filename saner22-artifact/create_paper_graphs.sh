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
version=$2

RES="./resources/$project/resources/"
D_OUTPUT="$HOME/results/section_graph/"
JOB="$project-$version"
TEX_OUTPUT="$D_OUTPUT/$JOB.tex"
PDF_OUTPUT="$D_OUTPUT/build"
template="./saner22-artifact/tikz_template.tex"

./pasta set_config $project

./analyses/tex_generator.R $RES/maintainers_section_graph/$version.csv

mkdir -p $D_OUTPUT $PDF_OUTPUT
./saner22-artifact/section_graph.py --output $TEX_OUTPUT --file $RES/R/$version.tex

lualatex -output-directory $PDF_OUTPUT -jobname $JOB "\\newcommand{\\version}{$JOB}\\newcommand{\\filename}{$TEX_OUTPUT}\\input{$template}"

cd $PDF_OUTPUT
mv -v *.pdf ..
rm -rfv $PDF_OUTPUT
