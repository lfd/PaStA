#!/usr/bin/env bash

# Copyright (c) OTH Regensburg, 2021-2022
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

set -e

PASTA=$(realpath "$(dirname "$0")/..")
DST="$HOME/pasta/results/overall"

# Already done on the resources branch
# cd "$PASTA"
# ./tools/analyse_project.sh linux
# ./tools/analyse_project.sh u-boot
# ./tools/analyse_project.sh xen
# ./tools/analyse_project.sh qemu

# ./fse22-artifact/cluster_compare_stats.py linux qemu u-boot xen

#  Concatenate results - create plots from paper
# cd "$PASTA/resources"
# ./concatenate_results.sh

# cd "$PASTA"
# ./fse22-artifact/paper-plots.R

# cd "$PASTA/resources/R"
# mkdir build
# for i in *_standalone.tex; do
# 	pdflatex -output-directory=build "$i"
# done
# mv -v build/*.pdf .
# rm -rfv build
# mkdir -p "$DST"
# cp -av * "$DST"

# # Create randomised clusters for cross-checking
# # Always take the latest major release of each project
# V_XEN=RELEASE-4.15.0
# V_U_BOOT=v2021.07
# V_QEMU=v6.1.0
# V_LINUX=v5.14
# 
# ./fse22-artifact/prepare_gui.sh xen $V_XEN
# ./fse22-artifact/prepare_gui.sh u-boot $V_U_BOOT
# ./fse22-artifact/prepare_gui.sh qemu $V_QEMU
# ./fse22-artifact/prepare_gui.sh linux $V_LINUX
# 
# mkdir -p "$PASTA/results"
# tar -czf "$PASTA/results/cluster_gui.tar.gz" -C "$PASTA/fse22-artifact" cluster_gui
