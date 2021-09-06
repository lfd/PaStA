#!/bin/bash

# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

set -e

./saner22-artifact/paper-plots.R

DST=/home/pasta/results/overall

cd resources/R
mkdir build
for i in *_standalone.tex; do
	pdflatex -output-directory=build $i
done

mv -v build/*.pdf .
rm -rfv build

mkdir -p $DST
cp -av * $DST
