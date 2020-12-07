#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2016, 2020
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

source("analyses/util.R")
library(plyr)

drop_versions <- c('3.0.9-rt26', '4.14.63-rt43')

# Global color palette
cols <- c("coral1",
          "cyan3",
          "#E69F00",
          "#56B4E9",
          "#009E73",
          "#0072B2",
          "#D55E00",
          "#CC79A7",
          "#999999",
          "#E69F00",
          "#56B4E9",
          "#009E73",
          "#0072B2",
          "#D55E00",
          "#CC79A7",
          "#999999",
          "#E69F00",
          "#56B4E9",
          "#009E73",
          "#0072B2",
          "#D55E00",
          "#CC79A7",
          "coral1",
          "cyan3",
          "#E69F00",
          "#56B4E9",
          "#009E73")

# Y-m-d Date converter
convertDate <- function(table, columns) {
  table[, columns] <- as.data.frame(lapply(table[, columns, drop = FALSE],
                                           as.Date))
  return(table)
}

commitcount <- function() {
  data <- as.data.frame(table(patch_groups$StackVersion))
  colnames(data) <- c("Version", "NumCommits")
  data <- merge(x = data,
                y =  stack_release_dates,
                by.x = "Version",
                by.y = "Version")

  # some sugar
  data <- data[, c(3,1,4,2)]

  mindate <- min(data$ReleaseDate)
  maxdate <- max(data$ReleaseDate)

  vgs <- unique(data$VersionGroup)
  vgs <- sort(vgs)

  xticks <- do.call("c", lapply(vgs, function(x)
    c(min(subset(data, VersionGroup == x)$ReleaseDate)#,
      #max(subset(commitcount, VersionGroup == x)$ReleaseDate)
    )
  ))

  p <- ggplot(data,
              aes(x = ReleaseDate,
                  y = NumCommits,
                  group = VersionGroup,
                  colour = VersionGroup)) +
    geom_line(size = 1.2) +
    ylim(200, max(data$NumCommits)) +
    scale_x_date(date_labels = "%b %Y",
                 limits = c(mindate, maxdate),
                 breaks = xticks) +
    theme_bw(base_size = 15) +
    scale_color_manual(values = cols) +
    xlab("Timeline") +
    ylab("Number of Patches") +
    theme(legend.position = "top",
          legend.title = element_blank(),
          axis.line = element_line(),
          axis.text.x = element_text(angle = 65,
                                     hjust = 1))

  printplot(p, 'commitcount')
}

# Diffstat analysis
diffstat <- function() {
  data <- diffstats
  data <- merge(x = data,
                y =  stack_release_dates,
                by.x = "Version",
                by.y = "Version")

  data$Sum <- data$Insertions + data$Deletions

  mindate <- min(data$ReleaseDate)
  maxdate <- max(data$ReleaseDate)

  vgs <- unique(data$VersionGroup)
  vgs <- sort(vgs)

  xticks <- do.call("c", lapply(vgs, function(x)
    c(min(subset(data, VersionGroup == x)$ReleaseDate))
  ))

  p <- ggplot(data) +
    geom_line(size = 1.2,
              aes(x = ReleaseDate,
                  y = Sum,
                  group = VersionGroup,
                  colour = VersionGroup)) +
    ylim(min(data$Sum),
         max(data$Sum)) +
    scale_x_date(date_labels = "%b %Y",
                 limits = c(mindate, maxdate),
                 breaks = xticks) +
    theme_bw(base_size = 15) +
    scale_color_manual(values = cols) +
    xlab("Timeline") +
    ylab("LOC deleted + inserted") +
    theme(legend.position = "top",
          legend.title = element_blank(),
          axis.line = element_line(),
          axis.text.x = element_text(angle = 65,
                                     hjust = 1))
  printplot(p, 'diffstat')
}

# Upstream analysis
upstream_analysis <- function() {
  p <- ggplot(upstream, aes(upstream$DateDiff)) +
    xlab("Days between release and upstream") +
    ylab("Upstream patch density [a.u.]") +
    theme_bw(base_size = 15) +
    theme(axis.line = element_line()) +
    #geom_histogram()
    geom_density() +
    geom_vline(xintercept = 0,
               colour = "red")

  printplot(p, 'upstream')
}

# Branch observation
branch_observation <- function() {

  pg <- merge(x = patch_groups[, c("PatchGroup", "StackVersion")],
              y = stack_release_dates[, c("VersionGroup", "Version")],
              by.x = "StackVersion",
              by.y = "Version",
              all.x = TRUE,
              all.y = FALSE)

  pg <- merge(x = pg,
              y = upstream[, c("PatchGroup", "Type")],
              by = "PatchGroup",
              all.x = TRUE,
              all.y = FALSE)

  pg$PatchGroup <- NULL

  pg$Type <- replace(pg$Type, is.na(pg$Type), "invariant")

  branch_observation <- ddply(pg, .(VersionGroup, StackVersion, Type), nrow)

  for (version in ord_version_grps) {
    observation <- subset(branch_observation, VersionGroup == version)
    plot <- ggplot(observation,
                   aes(x = StackVersion, y = V1, fill = Type)) +
      geom_bar(stat = "identity") +
      xlab("Stack Version") +
      theme(legend.position = "right",
            axis.title.y = element_blank(),
            axis.text.x = element_text(angle = 90,
                                       hjust = 1)) +
      scale_fill_discrete(name = version)
    printplot(plot, paste0('branch-observation-', version))
  }
}

# Stack future (maybe merge with branch observation)
stack_future <- function(stack_versions, filename) {

  pg <- merge(x = patch_groups[, c("PatchGroup", "StackVersion")],
              y = stack_release_dates[, c("VersionGroup", "Version")],
              by.x = "StackVersion",
              by.y = "Version",
              all.x = TRUE,
              all.y = FALSE)

  pg <- merge(x = pg,
              y = upstream[, c("PatchGroup", "Type")],
              by = "PatchGroup",
              all.x = TRUE,
              all.y = FALSE)

  pg$PatchGroup <- NULL

  pg$Type <- replace(pg$Type, is.na(pg$Type), "invariant")

  branch_observation <- ddply(pg, .(VersionGroup, StackVersion, Type), nrow)

  observation <- subset(branch_observation, StackVersion %in% stack_versions)
  plot <- ggplot(observation,
                 aes(x = StackVersion, y = V1, fill = Type)) +
    geom_bar(stat = "identity") +
    xlab("Stack Version") +
    ylab("Number of commits") +
    theme_bw(base_size = 15) +
    theme(legend.position = "top",
          axis.line = element_line(),
          axis.text.x = element_text(angle = 65,
                                     hjust = 1)) +
    scale_fill_discrete(name = "Types of patches")

  printplot(plot, paste0('stack-future-', filename))
}


### Program start ###
args <- commandArgs(trailingOnly = TRUE)

if (length(args) == 0) {
  project_name <- "SAMPLE"
  output_dir <- "foo"
  srcdir <- 'resources/PreemptRT/resources/R'
  persistent = FALSE
} else {
  project_name <- args[1]
  output_dir <- args[2]
  srcdir <- args[3]

  persistent = TRUE
}

get_csv <- function(file) {
  return(read_csv(file.path(srcdir, file)))
}

# Load all csv files
mainline_release_dates <- get_csv('mainline-release-dates')
stack_release_dates <- get_csv('stack-release-dates')
patch_groups <- get_csv('patches')
upstream <- get_csv('upstream')
occurrence <- get_csv('patch-occurrence')
release_sort <- get_csv('release-sort')
diffstats <- get_csv('diffstat')

# Convert columns containing dates
mainline_release_dates <- convertDate(mainline_release_dates,
                                      c("ReleaseDate"))
stack_release_dates <- convertDate(stack_release_dates,
                                   c("ReleaseDate"))
upstream <- convertDate(upstream, c("UpstreamCommitDate", "FirstStackOccurence"))

# Prepare Tables
upstream$DateDiff <- upstream$UpstreamCommitDate - upstream$FirstStackOccurence
upstream$DateDiff <- as.numeric(upstream$DateDiff, units="days")
upstream$Type <- sapply(upstream$DateDiff, function(x) {
  if (x < -1)
    "backport"
  else
    "forwardport"
})

# Filter strong outliers
diffstats <- diffstats %>% filter(!Version %in% drop_versions)
patch_groups <- patch_groups %>% filter(!StackVersion %in% drop_versions)
stack_release_dates <- stack_release_dates %>% filter(!Version %in% drop_versions)

# Set Version as ord. factors
ord_stack_ver = factor(unique(release_sort$Version),
                       ordered = TRUE,
                       levels = unique(release_sort$Version))

ord_version_grps = factor(unique(release_sort$VersionGroup),
                          ordered = TRUE,
                          levels = unique(release_sort$VersionGroup))

occurrence$OldestVersion <- factor(occurrence$OldestVersion,
                                   ordered = TRUE,
                                   levels = ord_stack_ver)

occurrence$LatestVersion <- factor(occurrence$LatestVersion,
                                   ordered = TRUE,
                                   levels = ord_stack_ver)

occurrence$FirstReleasedIn <- factor(occurrence$FirstReleasedIn,
                                   ordered = TRUE,
                                   levels = ord_stack_ver)

occurrence$LastReleasedIn <- factor(occurrence$LastReleasedIn,
                                   ordered = TRUE,
                                   levels = ord_stack_ver)

patch_groups$StackVersion <- factor(patch_groups$StackVersion,
                                    ordered = TRUE,
                                    levels = ord_stack_ver)

stack_release_dates$VersionGroup <- factor(stack_release_dates$VersionGroup,
                                           ordered = TRUE,
                                           levels = ord_version_grps)

stack_release_dates$Version <- factor(stack_release_dates$Version,
                                      ordered = TRUE,
                                      levels = ord_stack_ver)

fl_stack_versions <- factor(c(),
                            ordered = TRUE,
                            levels = ord_stack_ver)
f_stack_versions <- factor(c(),
                           ordered = TRUE,
                           levels = ord_stack_ver)
l_stack_versions <- factor(c(),
                           ordered = TRUE,
                           levels = ord_stack_ver)
for (i in ord_version_grps) {
  stacks_of_grp <- subset(stack_release_dates, VersionGroup == i)
  minver <- min(stacks_of_grp$Version)
  maxver <- max(stacks_of_grp$Version)
  fl_stack_versions[length(fl_stack_versions)+1] <- minver[1]
  fl_stack_versions[length(fl_stack_versions)+1] <- maxver[1]

  f_stack_versions[length(f_stack_versions)+1] <- minver[1]
  l_stack_versions[length(l_stack_versions)+1] <- maxver [1]
}

commitcount()
diffstat()
upstream_analysis()
branch_observation()
stack_future(fl_stack_versions, 'first-last')
stack_future(f_stack_versions, 'first')
stack_future(l_stack_versions, 'last')
