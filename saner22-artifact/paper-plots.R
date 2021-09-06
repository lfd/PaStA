#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

library(dplyr, warn.conflicts = FALSE)
library(ggplot2)
library(lubridate, warn.conflicts = FALSE)
library(reshape2)
library(tikzDevice)

f_characteristics <- '/home/pasta/PaStA/resources/characteristics.csv'
f_releases <- '/home/pasta/PaStA/resources/releases.csv'

d_dst = '/home/pasta/PaStA/resources/R'

dir.create(d_dst)

date.min <- '2011-01-01'
date.max <- '2030-12-31'

WIDTH <- 6.3
HEIGHT <- 5

my.theme <- theme_bw(base_size = 12) + theme(legend.position = "top")

printplot <- function(p, filename, ...) {
  plot(p, ...)
  
  filename <- file.path(d_dst, filename)
  #png(paste0(filename, '.png'), width=1920, height=1080/2)
  tikz(paste0(filename, '.tex'), width = WIDTH, height = HEIGHT, sanitize = TRUE, standAlone = FALSE)
  plot(p, ...)
  dev.off()

  tikz(paste0(filename, '_standalone.tex'), width = WIDTH, height = HEIGHT, sanitize = TRUE, standAlone = TRUE)
  plot(p, ...)
  dev.off()
}

read_csv <- function(filename) {
  return(read.csv(filename, header = TRUE, sep = ','))
}

load_characteristics <- function(filename) {
  data <- read_csv(filename)
  data$list.matches_patch <- as.logical(data$list.matches_patch)
  data$ignored <- as.logical(data$ignored)
  data$committer.correct <- as.logical(data$committer.correct)
  data$committer.xcorrect <- as.logical(data$committer.xcorrect)
  data <- data %>% mutate(date = as.Date(time))

  # Add week info
  data <- data %>% mutate(week = as.Date(cut(date, breaks = "week")))

  return(data)
}

load_releases <- function(filename) {
  data <- read_csv(filename)
  data <- data %>% mutate(date = as.Date(date))
}

fillup_missing_weeks <- function(data, key) {
  min.week <- min(data$week)
  delta.weeks <- days(max(data$week) - min.week)$day / 7

  all.weeks <- as.Date(sapply(0:delta.weeks, function(n) {
    return (as.character(min.week + weeks(n)))
  }))

  missing.weeks <- !(all.weeks %in% data$week)
  if (any(missing.weeks)) {
    frame <- data.frame(week = all.weeks[missing.weeks], col = 0)
    colnames(frame) <- colnames(data)

    return(rbind(data, frame))
  }
  return (data)
}

composition <- function(data, plot_name) {
  #relevant <- data %>% select(week, type, list)
  relevant <- data %>% select(project, week, type)
  
  other <- 'Other'
  relevant$type[relevant$type == 'process'] <- other
  relevant$type[relevant$type == 'linux-next'] <- other
  relevant$type[relevant$type == 'stable-review'] <- other
  relevant$type[relevant$type == 'bot'] <- other
  relevant$type[relevant$type == 'not-first'] <- other
  
  relevant$type[relevant$type == 'patch'] <- 'Regular Patch'
  relevant$type[relevant$type == 'not-linux'] <- 'Not Project'

  total <- relevant %>%
    group_by(project, week, type) %>%
    count(project, name = 'num')
  sum <- total %>%
    group_by(project, week) %>%
    summarise(num = sum(num)) %>%
    mutate(type = 'sum', .before = 'project')
  total <- bind_rows(total, sum)

  plot <- ggplot(total,
                 aes(x = week, y = num, color = type)) +
    geom_line() +
    geom_smooth() +
    #geom_vline(xintercept = releases$date, linetype="dotted") +
    #scale_y_sqrt(breaks = c(10, 100, 250, 500, 1000, 2000, 3000, 4000, 5000)) +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = "funky funky",
                 #                     breaks = releases$date,
                 #                     labels = releases$release)
    ) +
    labs(color = '') +
    facet_wrap(~project, scales = 'free_y') +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 45, hjust = 0))
  printplot(plot, plot_name)
}

# Only call for overall analysis!
patch_conform_by_week <- function(data, plot_name, field) {
  relevant <- data %>% select(project, week, !!field)

  true <- relevant %>% filter(!!field == TRUE) %>% select(-!!field) %>% group_by(project, week) %>% count(name = 'correct')
  false <- relevant %>% filter(!!field == FALSE) %>% select(-!!field) %>% group_by(project, week) %>% count(name = 'incorrect')
  not_integrated <- relevant %>% filter(is.na(!!field)) %>% select(-!!field) %>% group_by(project, week) %>% count(name = 'not_integrated')
  total <- relevant %>% select(project, week) %>% group_by(project, week) %>% count(name = 'total')

  # Fill up weeks with no values with zeroes
  total <- total %>% group_by(project) %>% group_modify(fillup_missing_weeks)

  # We must also merge weeks with no ignored patches, so all.x/y = TRUE
  df <- merge(x = true, y = false, by = c('project', 'week'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = not_integrated, by = c('project', 'week'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = total, by = c('project', 'week'), all.x = TRUE, all.y = TRUE)
  # Then, replace NA by 0
  df[is.na(df)] <- 0

  df <- melt(df, id.vars = c('project', 'week'))

  p <- ggplot(df, aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth() +
    #geom_vline(xintercept = releases$date, linetype="dotted") +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
    facet_wrap(~project, scales = 'free') +
    ggtitle(plot_name) +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 90, hjust = 0),
          legend.title = element_blank())
  printplot(p, plot_name)
}

# Only call for overall analysis!
patch_conform_ratio <- function(data, plot_name) {
  relevant <- data %>% select(project, week, committer.correct, committer.xcorrect)

  true <- relevant %>% filter(committer.correct == TRUE) %>% select(project, week) %>% group_by(project, week) %>% count(name = 'correct')
  false <- relevant %>% filter(committer.correct == FALSE) %>% select(project, week) %>% group_by(project, week) %>% count(name = 'incorrect')

  xtrue <- relevant %>% filter(committer.xcorrect == TRUE) %>% select(project, week) %>% group_by(project, week) %>% count(name = 'xcorrect')
  xfalse <- relevant %>% filter(committer.xcorrect == FALSE) %>% select(project, week) %>% group_by(project, week) %>% count(name = 'xincorrect')


  # Fill up weeks with no values with zeroes
  true <- true %>% group_by(project) %>% group_modify(fillup_missing_weeks)

  # We must also merge weeks with no ignored patches, so all.x/y = TRUE
  df <- merge(x = true, y = false, by = c('project', 'week'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = xtrue, by = c('project', 'week'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = xfalse, by = c('project', 'week'), all.x = TRUE, all.y = TRUE)
  # Then, replace NA by 0
  df[is.na(df)] <- 0

  df <- df %>%
    mutate(ratio_correct = correct / (correct + incorrect)) %>%
    mutate(ratio_xcorrect = xcorrect / (xcorrect + xincorrect)) %>%
    select(project, week, ratio_correct, ratio_xcorrect)

  df <- melt(df, id.vars = c('project', 'week'))

  p <- ggplot(df, aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth() +
    #geom_vline(xintercept = releases$date, linetype="dotted") +
    ylab('Ratio of correctly integrated patches') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                 #                    breaks = releases$date,
                 #                    labels = releases$release)
    ) +
    facet_wrap(~project, scales = 'free_y') +
    ggtitle(plot_name) +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 90, hjust = 0),
          legend.title = element_blank())
  printplot(p, plot_name)

}

patch_conform_ratio_list <- function(data, plot_name) {
  relevant <- data %>% select(week, committer.correct, committer.xcorrect, list)

  true <- relevant %>% filter(committer.correct == TRUE) %>% select(week, list) %>% group_by(week, list) %>% count(name = 'correct')
  false <- relevant %>% filter(committer.correct == FALSE) %>% select(week, list) %>% group_by(week, list) %>% count(name = 'incorrect')

  xtrue <- relevant %>% filter(committer.xcorrect == TRUE) %>% select(week, list) %>% group_by(week, list) %>% count(name = 'xcorrect')
  xfalse <- relevant %>% filter(committer.xcorrect == FALSE) %>% select(week, list) %>% group_by(week, list) %>% count(name = 'xincorrect')


  # Fill up weeks with no values with zeroes
  true <- true %>% group_by(list) %>% group_modify(fillup_missing_weeks)

  # We must also merge weeks with no ignored patches, so all.x/y = TRUE
  df <- merge(x = true, y = false, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = xtrue, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = xfalse, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  # Then, replace NA by 0
  df[is.na(df)] <- 0
  
  rel <- releases %>% filter(project == 'linux') %>% select(-project)

  df <- df %>%
    mutate(ratio_correct = correct / (correct + incorrect)) %>%
    mutate(ratio_xcorrect = xcorrect / (xcorrect + xincorrect)) %>%
    select(week, list, ratio_correct, ratio_xcorrect)

  df <- melt(df, id.vars = c('week', 'list'))

  p <- ggplot(df, aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth() +
    #geom_vline(xintercept = releases$date, linetype="dotted") +
    ylab('Ratio of correctly integrated patches') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name = 'Linux',
                                     breaks = rel$date,
                                     labels = rel$release)
    ) +
    facet_wrap(~list, scales = 'free') +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 90, hjust = 0),
          legend.title = element_blank())
  printplot(p, plot_name)

}



if (!exists('raw_data')) {
  raw_data <- load_characteristics(f_characteristics)
}

if (!exists('releases')) {
  releases <- load_releases(f_releases)
}

# Filter strong outliers, select the appropriate time window
# and only patches with type 'patch'
filtered_data <- raw_data %>%
  filter(from != 'baolex.ni@intel.com') %>%
  filter(week < date.max) %>%
  filter(week > date.min)

filtered_data <- rbind(
  filtered_data %>% filter(project != 'linux'),
  filtered_data %>% filter(project == 'linux') %>% filter(date > '2011-05-01')
)

# Plot the composition for the whole project
all <- filtered_data %>% select(-c(list.matches_patch))
all$list <- 'Overall'
all <- all %>% distinct()
composition(all, 'composition.overall')

# Once the composition is plotted, we can limit on the type 'patch'. For the
# ignored patches analysis, we're only interested in patches that patch the project,
# and were written by real humans.
filtered_data_all <- all %>%
  filter(type == 'patch') %>%
  select(-type)

patch_conform_by_week(all, 'conform', quo(committer.correct))
patch_conform_by_week(all, 'xconform', quo(committer.xcorrect))

patch_conform_ratio(filtered_data_all, 'conform_ratio.all')

linux <- filtered_data %>%
  filter(project == 'linux') %>%
  select(-project) %>%
  filter(list %in% c('linux-kernel@vger.kernel.org',
                     'linux-arm-kernel@lists.infradead.org',
                     'netdev@vger.kernel.org',
                     'netfilter-devel@vger.kernel.org'
                     ))

patch_conform_ratio_list(linux, 'conform.linux')
