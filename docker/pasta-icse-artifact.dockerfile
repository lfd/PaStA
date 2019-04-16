# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM pasta:linux

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

RUN wget https://cdn.lfdr.de/PaStA/LKML-2012-05.mbox

ADD https://api.github.com/repos/lfd/PaStA/git/refs/heads/icse-artifact /dev/null
RUN git -C PaStA pull
RUN git -C PaStA checkout -b icse-artifact --track origin/icse-artifact
RUN git -C PaStA submodule update
RUN cd PaStA && ./pasta mbox_prepare lkml-2012-05 ~/LKML-2012-05.mbox
RUN cd PaStA && ./pasta cache -create all

ADD icse/icse-artifact-analysis.sh icse-artifact-analysis.sh
