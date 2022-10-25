# Copyright (c) OTH Regensburg, 2017-2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

FROM ubuntu:21.04

MAINTAINER Ralf Ramsauer "ralf.ramsauer@oth-regensburg.de"

ENV DEBIAN_FRONTEND noninteractive
ENV LANG="C.UTF-8"
ENV LC_ALL="C.UTF-8"

RUN apt update && apt -y dist-upgrade

# install PaStA dependencies
RUN apt install -y --no-install-recommends \
	build-essential \
	gfortran \
	git \
	libblas-dev \
	liblapack-dev \
	libpng-dev \
	locales \
	patchutils \
	procmail \
	python3-dev \
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
	texlive \
	texlive-pictures \
	texlive-latex-extra \
	vim \
	wget

# install some more python dependencies that are not provided by Ubuntu's repo
RUN pip3 --no-cache-dir install \
	anytree \
	dateparser \
	Levenshtein

RUN useradd -m -G sudo -s /bin/bash pasta && echo "pasta:pasta" | chpasswd
USER pasta
WORKDIR /home/pasta

ENV R_LIBS_USER /home/pasta/R/
RUN mkdir -p $HOME/.R $R_LIBS_USER
RUN echo MAKEFLAGS = -j$(($(nproc)/4)) > ~/.R/Makevars

RUN R -e "install.packages(c('assertthat', 'dplyr', 'ggplot2', 'igraph', 'lubridate', 'reshape2', 'RColorBrewer', 'tikzDevice'), Ncpus = 4, clean = TRUE, lib = '${R_LIBS_USER}')"
