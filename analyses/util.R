# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2020-2021
#
# Author:
#   Pia Eichinger <pia.eichinger@st.oth-regensburg.de>
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

library(dplyr, warn.conflicts = FALSE)
library(ggplot2)
library(lubridate, warn.conflicts = FALSE)
library(reshape2)
library(tikzDevice)

d_dst <- '/tmp/R'
project <- read.csv('config', header=FALSE)$V1
d_resources <- file.path('resources', project, 'resources')

WIDTH <- 6.3
HEIGHT <- 5

my.theme <- theme_bw(base_size = 8) +
            theme(legend.position = "top")

create_dstdir <- function(path_vec){
	dir.create(d_dst, showWarnings = FALSE, recursive = TRUE)
	for (i in path_vec) {
	  dir.create(file.path(d_dst, i), showWarnings = FALSE)
	}
}

read_csv <- function(filename){
  return(read.csv(filename, header = TRUE, sep=","))
}

printplot <- function(p, filename, ...) {
  plot(p, ...)

  filename <- file.path(d_dst, filename)
  #png(paste0(filename, '.png'), width = 1920, height = 1080)
  #plot(p, ...)
  #dev.off()

  tikz(paste0(filename, '.tex'), width = WIDTH, height = HEIGHT, sanitize=TRUE, standAlone = TRUE)
  plot(p, ...)
  dev.off()
}

dir.create(d_dst, showWarnings = FALSE)
