# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM ubuntu:19.04

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

ENV DEBIAN_FRONTEND noninteractive

RUN apt update
RUN apt -y dist-upgrade

# install PaStA dependencies
RUN apt install -y python3-sklearn python3-git python3-pygit2 \
	python3-fuzzywuzzy python3-flaskext.wtf python3-pip \
	python3-toml python3-tqdm git procmail wget sudo vim locales

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

RUN useradd -m -G sudo -s /bin/bash pasta
RUN echo "pasta:pasta" | chpasswd

USER pasta
WORKDIR /home/pasta

# install some more python dependencies that are not provided by Ubuntu's repo
RUN pip3 install --user dateparser flask-bootstrap flask-nav anytree
