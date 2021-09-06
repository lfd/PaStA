# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:saner22-stage1

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

# Generate clusters and analysis results
WORKDIR /home/pasta/PaStA
### FIXME REMOVE THIS WHEN FINISHED WITH PREPARATION
RUN git checkout saner22-artifact

# Linux analysis - the short way
WORKDIR /home/pasta/PaStA/resources/linux/resources
RUN pbzip2 -dv patch-groups.bz2 characteristics.csv.bz2
WORKDIR /home/pasta/PaStA

RUN ./tools/analyse_project.sh linux
RUN ./tools/analyse_project.sh u-boot
RUN ./tools/analyse_project.sh xen
RUN ./tools/analyse_project.sh qemu

# Concatenate Results - Create plots from paper
WORKDIR /home/pasta/PaStA/resources
RUN ./concatenate_results.sh

WORKDIR /home/pasta/PaStA
RUN ./saner22-artifact/create_overall_results.sh

# Create randomised clusters for cross-checking
# Always take the latest major release of each project
ENV V_XEN=RELEASE-4.15.0
ENV V_U_BOOT=v2021.07
ENV V_QEMU=v6.1.0
ENV V_LINUX=v5.14

RUN ./saner22-artifact/prepare_gui.sh xen $V_XEN
RUN ./saner22-artifact/prepare_gui.sh u-boot $V_U_BOOT
RUN ./saner22-artifact/prepare_gui.sh qemu $V_QEMU
RUN ./saner22-artifact/prepare_gui.sh linux $V_LINUX

WORKDIR /home/pasta/PaStA/saner22-artifact
RUN mkdir -p /home/pasta/results && tar -czf /home/pasta/results/cluster_gui.tar.gz ./cluster_gui
WORKDIR /home/pasta/PaStA

# Create cluster graphs for the paper
RUN ./saner22-artifact/create_paper_graphs.sh xen $V_XEN
RUN ./saner22-artifact/create_paper_graphs.sh u-boot $V_U_BOOT

# Create Daumenkino
RUN ./saner22-artifact/daumenkino.sh linux
