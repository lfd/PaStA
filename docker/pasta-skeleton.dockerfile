# Copyright (c) OTH Regensburg, 2017-2018
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM ubuntu:20.04

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

ENV DEBIAN_FRONTEND noninteractive
ENV LANG="C.UTF-8"
ENV LC_ALL="C.UTF-8"

RUN apt update && apt -y dist-upgrade

# install PaStA dependencies
RUN apt install -y --no-install-recommends \
	build-essential \
	git \
	locales \
	patchutils \
	procmail \
	python3-dev \
	python3-flaskext.wtf \
	python3-fuzzywuzzy \
	python3-git \
	python3-networkx \
	python3-pip \
	python3-pygit2 \
	python3-requests \
	python3-setuptools \
	python3-sklearn \
	python3-toml \
	python3-tqdm \
	python3-wheel \
	r-base \
	sudo \
	vim \
	wget

# install some more python dependencies that are not provided by Ubuntu's repo
RUN pip3 --no-cache-dir install \
	dateparser \
	flask-bootstrap \
	flask-nav anytree

RUN R -e "install.packages(c('dplyr', 'ggplot2', 'lubridate', 'plyr', 'reshape2', 'tikzDevice'), clean = TRUE)"

RUN useradd -m -G sudo -s /bin/bash pasta && echo "pasta:pasta" | chpasswd

USER pasta
WORKDIR /home/pasta
