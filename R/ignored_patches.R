#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2019
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
} else {
  d_dst <- args[1]
  f_characteristics <- args[2]
}

dir.create(d_dst, showWarnings = FALSE)

load_csv <- function(filename) {
  data <- read.csv(filename, header = TRUE, sep=",")
  data$list_matches_patch <- as.logical(data$list_matches_patch)
  data$ignored <- as.logical(data$ignored)
  data <- data %>% mutate(date = as.Date(time))

  # Add week info
  data <- data %>% mutate(week = as.Date(cut(date, breaks = "week")))

  return(data)
}

if (!exists('raw_data')) {
  raw_data <- load_csv(f_characteristics)
}

filtered_data <- raw_data

# Filter strong outliers
filtered_data <- filtered_data %>% filter(from != 'baolex.ni@intel.com')

filtered_data <- filtered_data %>%
  filter(week > '2011-05-10')

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

  df <- merge(x = true, y = false, by = c('week', 'list'))
  df <- merge(x = df, y = total, by = c('week', 'list'))

  df$fraction <- df$ignored / df$total

  df <- melt(df, id.vars = c('week', 'list'))

  relevant <- df %>% filter(variable == true_case | variable == 'total')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm") +
    scale_y_log10() +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    theme_bw(base_size = 15) +
    # theme(legend.position = 'top') +
    labs(color = '') +
    facet_wrap(~list, scales = 'free')
  printplot(plot, 'ignored_by_week_total', 3)


  relevant <- df %>% filter(variable == 'ignored') #%>% select(week, value)
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm", fill = 'green', colour = 'black') +
    geom_smooth(fill = 'blue', colour = 'black') +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    xlab('Date') +
    ylab('Total number of ignored patches per week') +
    theme(legend.position = 'None') +
    facet_wrap(~list, scales = 'free')
  printplot(plot, 'ignored_by_week_ignored_only', 3)

  relevant <- df %>% filter(variable == 'fraction')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm", fill = 'green', colour = 'black') +
    geom_smooth(fill = 'blue', colour = 'black') +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    #scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
    #                      breaks = seq(0.01, 0.06, by = 0.01)) +
    #scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%")) +
    xlab('Date') +
    ylab('Ratio of ignored patches') +
    #ylab('Ratio of correctly addressed maintainers') +
    theme(legend.position = 'None') +
    facet_wrap(~list, scales = 'free')
      printplot(plot, 'ignored_by_week_fraction', 3)
}

ignored_by_rc <- function(data) {
  data <- data %>% select('list', 'kv', 'rc', 'ignored')

  total <- ddply(data, .(list, kv, rc), nrow)
  colnames(total) <- c('list', 'kv', 'rc', 'total')

  ignored <- data %>% filter(ignored == TRUE)
  ignored <- ddply(ignored, .(list, kv, rc), nrow)
  colnames(ignored) <- c('list', 'kv', 'rc', 'ignored')

  df <- merge(x = total, y = ignored, by = c('list', 'kv', 'rc'))
  df$fraction <- df$ignored / df$total
  df <- melt(df, id.vars = c('list', 'kv', 'rc'))

  relevant <- df %>% filter(variable == 'fraction') %>% select(list, kv, rc, value)

  plot <- ggplot(relevant,
                 aes(x = rc, y = value, group = rc)) +
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

#filtered_data <- filtered_data %>% filter(list_matches_patch == TRUE)

selection <- filtered_data %>%
  filter(list %in% c(#'cocci@systeme.lip6.fr',
                     'linuxppc-dev@lists.ozlabs.org',
                     'linux-arm-kernel@lists.infradead.org',
                     #'linux-clk@vger.kernel.org',
                     #'linux-bluetooth@vger.kernel.org'
                     'linux-mips@vger.kernel.org',
                     #'linux-parisc@vger.kernel.org',
                     'linux-pci@vger.kernel.org',
                     'netdev@vger.kernel.org',
                     'linux-kernel@vger.kernel.org'
                     #'linux-media@vger.kernel.org',
                     #'linux-fsdevel@vger.kernel.org'
                     ))

all <- filtered_data
all$list <- 'Overall'
all <- all %>% distinct

#ignore_rate_by_years(all)

ignored_by_week(selection)
#ignored_by_week(all)

#ignored_by_rc(selection)
#ignored_by_rc(all)

#filtered_data <- filtered_data %>% filter(kv != 'v2.6.39')
#scatterplots(all)
#week_scatterplots(all)