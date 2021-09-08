# Copyright (c) OTH Regensburg, 2017-2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:skeleton

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

# prepare PaStA
RUN git clone https://github.com/lfd/PaStA.git
WORKDIR /home/pasta/PaStA

RUN git submodule init
RUN git submodule update
RUN git -C resources checkout master
RUN git -C resources submodule init
