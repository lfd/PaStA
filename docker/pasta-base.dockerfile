# Copyright (c) OTH Regensburg, 2017-2018
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
RUN git -C PaStA submodule init
RUN git -C PaStA submodule update
RUN git -C PaStA/resources checkout master

# workaround to get the latest state of the repository
ADD https://api.github.com/repos/lfd/PaStA/git/refs/heads/master /dev/null
RUN git -C PaStA pull

ADD https://api.github.com/repos/lfd/PaStA-resources/git/refs/heads/master /dev/null
RUN git -C PaStA/resources pull

RUN git -C PaStA/resources submodule init
