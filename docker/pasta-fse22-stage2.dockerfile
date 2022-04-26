# Copyright (c) OTH Regensburg, 2021-2022
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:fse22-stage1

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

# Generate clusters and analysis results
WORKDIR /home/pasta/PaStA
### FIXME REMOVE THIS WHEN FINISHED WITH PREPARATION
#RUN git checkout fse22-artifact
# just call it wip for the moment
RUN git checkout wip

# Linux analysis - the short way
WORKDIR /home/pasta/PaStA/resources/linux/resources
RUN lzma -dv patch-groups.lzma characteristics.csv.lzma
WORKDIR /home/pasta/PaStA

RUN ./tools/analyse_project.sh linux
RUN ./tools/analyse_project.sh u-boot
RUN ./tools/analyse_project.sh xen
RUN ./tools/analyse_project.sh qemu

# Concatenate Results - Create plots from paper
WORKDIR /home/pasta/PaStA/resources
RUN ./concatenate_results.sh

WORKDIR /home/pasta/PaStA
RUN ./fse22-artifact/create_overall_results.sh

# Create randomised clusters for cross-checking
# Always take the latest major release of each project
ENV V_XEN=RELEASE-4.15.0
ENV V_U_BOOT=v2021.07
ENV V_QEMU=v6.1.0
ENV V_LINUX=v5.14

RUN ./fse22-artifact/prepare_gui.sh xen $V_XEN
RUN ./fse22-artifact/prepare_gui.sh u-boot $V_U_BOOT
RUN ./fse22-artifact/prepare_gui.sh qemu $V_QEMU
RUN ./fse22-artifact/prepare_gui.sh linux $V_LINUX

WORKDIR /home/pasta/PaStA/fse22-artifact
RUN mkdir -p /home/pasta/results && tar -czf /home/pasta/results/cluster_gui.tar.gz ./cluster_gui
WORKDIR /home/pasta/PaStA
