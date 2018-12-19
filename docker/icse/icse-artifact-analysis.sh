#!/bin/bash
#
# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

DLR=0.4
TA=0.82
W=0.3

RES=resources/linux/resources/mbox-result
GT=resources/linux/resources/2012-05-mbox-result.groundtruth

cd ~/PaStA

./pasta analyse -mbox init
./pasta analyse -mbox rep -dlr $DLR
./pasta rate -ta $TA -w $W -ti 1
./pasta analyse -mbox upstream -dlr $DLR
./pasta rate -ta $TA -w $W -ti 1

./pasta compare_clusters -fm $GT $RES
