#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2020
#
# Author:
#   Pia Eichinger <pia.eichinger@st.oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

library(dplyr)
library(ggplot2)
library(lubridate)
library(reshape2)
library(tikzDevice)

d_dst <- '/tmp/R'

create_dstdir <- function(path_vec){
	for (i in path_vec) {
	  dir.create(file.path(d_dst, i), showWarnings = FALSE)
	}
}

read_csv <- function(filename){
  return(read.csv(filename, header = TRUE, sep=","))
}

printplot <- function(plot, filename, width_correction) {
  print(plot)
  filename <- file.path(d_dst, filename)
  ggsave(paste0(filename, '.pdf'), plot, dpi = 300, width = 297, height = 210, units = 'mm', device = 'pdf')
  ggsave(paste0(filename, '.png'), plot, dpi = 300, width = 297, height = 210, units = 'mm', device = 'png')
  tikz(paste0(filename, '.tex'), width = 6.3 + width_correction, height = 5)
  print(plot)
  dev.off()
}
