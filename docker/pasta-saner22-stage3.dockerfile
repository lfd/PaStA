# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:saner22-stage2

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

# Clone all MLs that are related to linux
WORKDIR /home/pasta/PaStA/resources/linux
RUN git submodule update .
