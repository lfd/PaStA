#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2019-2020
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

library(dplyr)
library(ggplot2)
library(lubridate)
library(plyr)
library(reshape2)
library(tikzDevice)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) {
  d_dst <- '/tmp/R'
  f_characteristics <- 'resources/linux/resources/characteristics.csv'
  f_releases <- 'resources/linux/resources/releases.csv'
} else {
  d_dst <- args[1]
  f_characteristics <- args[2]
  f_releases <- args[3]
}

dir.create(d_dst, showWarnings = FALSE)

load_csv <- function(filename) {
  data <- read.csv(filename, header = TRUE, sep=",")
  data$list.matches_patch <- as.logical(data$list.matches_patch)
  data$ignored <- as.logical(data$ignored)
  data <- data %>% mutate(date = as.Date(time))

  # Add week info
  data <- data %>% mutate(week = as.Date(cut(date, breaks = "week")))

  return(data)
}

load_releases <- function(filename) {
  data <- read.csv(filename, header = TRUE, sep=",")
  data <- data %>% mutate(date = as.Date(date))
}

if (!exists('raw_data')) {
  raw_data <- load_csv(f_characteristics)
}

if (!exists('releases')) {
  releases <- load_releases(f_releases)
}

filtered_data <- raw_data

# Filter strong outliers
filtered_data <- filtered_data %>%
  filter(from != 'baolex.ni@intel.com') %>%
  filter(week < '2020-06-01') %>%
  filter(week > '2017-01-01')

fname <- function(file, extension) {
  return(file.path(d_dst, paste(file, extension, sep='')))
}

yearpp <- function(date) {
  ymd(paste((year(date) + 1), '0101', sep = ''))
}

printplot <- function(plot, filename, width_correction) {
  print(plot)
  ggsave(fname(filename, '.pdf'), plot, dpi = 300, width = 8, device = 'pdf')

  tikz(fname(filename, '.tex'), width = 6.3 + width_correction, height = 5)
  print(plot)
  dev.off()
}


ignore_rate_by_years <- function(data) {
  calc_ign_rate <- function(data) {
    total = nrow(data)
    ignored = nrow(data %>% filter(ignored == TRUE))
    return(ignored / total)
  }

  data <- data %>% select(date, ignored)
  date_begin = as.Date(cut(min(data$date), breaks = "year"))
  date_end = yearpp(max(data$date))
  cat('Overall ignored rate: ', calc_ign_rate(data), '\n')

  while (date_begin < date_end) {
    date_next = yearpp(date_begin)

    relevant <- data %>% filter(date >= date_begin & date < date_next)
    cat('Ignored rate', year(date_begin) ,': ', calc_ign_rate(relevant), '\n')

    date_begin <- date_next
  }
}

ignored_by_week <- function(data) {
  variable <- 'ignored'
  true_case <- 'ignored'
  false_case <- 'not_ignored'

  relevant <- data %>% select(week, ignored, list)

  count_predicate <- function(data, row, value, name) {
    ret <- relevant %>% filter(UQ(as.name(row)) == value)
    ret <- ddply(ret, .(week, list), nrow)
    colnames(ret) <- c('week', 'list', name)
    return(ret)
  }

  true <- count_predicate(relevant, variable, TRUE, true_case)
  false <- count_predicate(relevant, variable, FALSE, false_case)

  total <- ddply(relevant, .(week, list), nrow)
  colnames(total) <- c('week', 'list', 'total')

  fillup_missing_weeks <- function(data, key) {
    min.week <- min(data$week)
    delta.weeks <- days(max(data$week) - min.week)$day / 7

    all.weeks <- as.Date(sapply(0:delta.weeks, function(n) {
      return (as.character(min.week + weeks(n)))
    }))

    missing.weeks <- !(all.weeks %in% data$week)
    if (any(missing.weeks)) {
      return(rbind(data, data.frame(week=all.weeks[missing.weeks], total=0)))
    }
    return (data)
  }

  # Fill up weeks with no values with zeroes
  total <- total %>% group_by(list) %>% group_modify(fillup_missing_weeks)

  # We must also merge weeks with no ignored patches, so all.x/y = TRUE
  df <- merge(x = true, y = false, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = total, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  # Then, replace NA by 0
  df[is.na(df)] <- 0

  df$fraction <- df$ignored / df$total

  df <- melt(df, id.vars = c('week', 'list'))

  relevant <- df %>% filter(variable == true_case | variable == 'total')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth() +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    scale_y_sqrt(breaks = c(10, 100, 250, 500, 1000, 2000, 3000, 4000, 5000)) +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name="Linux Releases",
                                     breaks = releases$date,
                                     labels = releases$release)
                 ) +
    theme_bw(base_size = 15) +
    theme(legend.position = 'top',
          axis.text.x.top = element_text(angle = 45, hjust = 0)) +
    labs(color = '') +
    facet_wrap(~list, scales = 'free')
  printplot(plot, 'ignored_by_week_total', 4.5)

  relevant <- df %>% filter(variable == 'ignored') #%>% select(week, value)
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm", fill = 'green', colour = 'black') +
    geom_smooth(fill = 'blue', colour = 'black') +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name="Linux Releases",
                                     breaks = releases$date,
                                     labels = releases$release)) +
    xlab('Date') +
    ylab('Total number of ignored patches per week') +
    theme(legend.position = 'None',
          axis.text.x.top = element_text(angle = 45, hjust = 0)) +
    facet_wrap(~list, scales = 'free')
  printplot(plot, 'ignored_by_week_ignored_only', 4.5)

  relevant <- df %>% filter(variable == 'fraction')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm", fill = 'green', colour = 'black') +
    geom_smooth(fill = 'blue', colour = 'black') +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name="Linux Releases",
                                     breaks = releases$date,
                                     labels = releases$release)) +
    #scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
    #                   breaks = seq(0.01, 0.06, by = 0.01)) +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%")) +
    xlab('Date') +
    ylab('Ratio of ignored patches') +
    #ylab('Ratio of correctly addressed maintainers') +
    theme(legend.position = 'None',
          axis.text.x.top = element_text(angle = 45, hjust = 0)) +
    facet_wrap(~list, scales = 'free')
      printplot(plot, 'ignored_by_week_fraction', 4.5)
}

ignored_by_rc <- function(data) {
  data <- data %>% select('list', 'v.kv', 'v.rc', 'ignored')

  total <- ddply(data, .(list, v.kv, v.rc), nrow)
  colnames(total) <- c('list', 'v.kv', 'v.rc', 'total')

  ignored <- data %>% filter(ignored == TRUE)
  ignored <- ddply(ignored, .(list, v.kv, v.rc), nrow)
  colnames(ignored) <- c('list', 'v.kv', 'v.rc', 'ignored')

  df <- merge(x = total, y = ignored, by = c('list', 'v.kv', 'v.rc'))
  df$fraction <- df$ignored / df$total
  df <- melt(df, id.vars = c('list', 'v.kv', 'v.rc'))

  relevant <- df %>% filter(variable == 'fraction') %>% select(list, v.kv, v.rc, value)

  plot <- ggplot(relevant,
                 aes(x = v.rc, y = value, group = v.rc)) +
    geom_boxplot() +
    theme_bw(base_size =  15) +
    scale_x_continuous(breaks = 0:10,
                       labels = c('MW', 1:10)) +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
                       breaks = seq(0.01, 0.06, by = 0.01)) +
    xlab('Development Stage (-rc)') +
    ylab('Probability that patch is ignored') +
    facet_wrap(~list)
  printplot(plot, 'ignored_by_rc', 0)
}

  scatterplots <- function(data) {
  data <- filtered_data

  ignored <- data %>% filter(ignored == TRUE) %>% select(from) %>% count
  colnames(ignored) <- c('from', 'ignored')

  not_ignored <- data %>% filter(ignored == FALSE) %>% select(from) %>% count
  colnames(not_ignored) <- c('from', 'not_ignored')

  total <- data %>% select(from) %>% count
  colnames(total) <- c('from', 'total')

  df <- merge(x = ignored, y = not_ignored, by = c('from'))
  df <- merge(x = df, y = total, by = c('from'))

  df$ratio <- df$ignored / df$total

  relevant <- df %>% filter(total < 4000) %>% filter(ignored < 400)
  # relevant <- df
  plot <- ggplot(relevant, aes(x = total, y = ignored)) +
    geom_point() + scale_x_sqrt() + scale_y_sqrt() + geom_smooth() +
    xlab('Number of patches by author') +
    ylab('Number of ignored patches') +
    theme_bw(base_size = 15)
  printplot(plot, 'foo5', 2)

  relevant <- df %>% filter(total < 101)
  plot <- ggplot(relevant, aes(x = total, y = ignored)) +
    geom_point() + geom_density2d()
  printplot(plot, 'foo6', 0)

    relevant <- df %>% filter(total < 101)
  plot <- ggplot(relevant, aes(x = total, y = ratio)) +
    geom_point() + geom_density2d()
  printplot(plot, 'foo7', 0)
}

week_scatterplots <- function(data) {
  data <- filtered_data

  data <- data %>% select(week, ignored)

  total <- ddply(data, .(week), nrow)
  colnames(total) <- c('week', 'total')

  ignored <- ddply(data %>% filter(ignored == TRUE), .(week), nrow)
  colnames(ignored) <- c('week', 'ignored')

  df = merge(x = total, y = ignored, by = c('week'))

  plot <- ggplot(df, aes(x = total, y = ignored)) +
    geom_point() +
    theme_bw(base_size = 15) +
    xlab('Patches per week') +
    ylab('Number of ign. patches per week')
  printplot(plot, 'ignored_week_scatter', 0)
}

all <- filtered_data
# When we consider 'all' lists, we need to remove mails that were sent to multiple lists.
# As a consequence, we need to drop the list.matches_patch column, as this value is tied to
# the list information.
all <- all %>% select(-c(list.matches_patch))
all$list <- 'Overall'
all <- all %>% distinct()

selection <- filtered_data %>%
  filter(list %in% c('linux-arm-kernel@lists.infradead.org',
                     'netdev@vger.kernel.org',
                     'linuxppc-dev@lists.ozlabs.org',
                     'alsa-devel@alsa-project.org'
                     ))

#ignore_rate_by_years(all)

ignored_by_week(selection)
ignored_by_week(all)

#ignored_by_rc(selection)
#ignored_by_rc(all)

#filtered_data <- filtered_data %>% filter(v.kv != 'v2.6.39')
#scatterplots(all)
#week_scatterplots(all)