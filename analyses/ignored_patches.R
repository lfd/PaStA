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

mindate <- '2017-01-01'
maxdate <- '2020-07-01'

load_characteristics <- function(filename) {
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

  data <- data %>% filter(type == 'patch') %>% select(date, ignored)
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

ignored_by_week <- function(data, plot_name) {
  variable <- 'ignored'
  true_case <- 'ignored'
  false_case <- 'not_ignored'

  relevant <- data %>% filter(type == 'patch') %>% select(week, ignored, list)

  count_predicate <- function(data, row, value, name) {
    ret <- relevant %>% filter(UQ(as.name(row)) == value)
    # We have a special case if nrow(ret) == 0. R does introduce new
    # column names in that case.
    if (nrow(ret) == 0) {
      # Pseudo-conversion, this is just used to get the correct data frame format
      `$`(ret, name) <- as.integer(`$`(ret, name))
      ret <- ret[c('week', 'list', name)]
      return(ret)
    }
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

  df$fraction <- ifelse(df$total==0, NA, df$ignored / df$total)

  df <- melt(df, id.vars = c('week', 'list'))

  # First plot: Plot the ignored patches and the absolute amount of patches.
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
  filename <- paste('ignored_total', plot_name, sep = '/')
  printplot(plot, filename, 4.5)

  # Second plot: plot ignored patches in absolute numbers
  relevant <- df %>% filter(variable == 'ignored')
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
  filename <- paste('ignored_absolute', plot_name, sep = '/')
  printplot(plot, filename, 4.5)

  # Third plot: plot the ignored patches as a fraction of all patches
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
  filename <- paste('ignored_fraction', plot_name, sep = '/')
  printplot(plot, filename, 4.5)
}

composition <- function(data, plot_name) {
  relevant <- data %>% select(week, type, list)

  sum <- ddply(relevant, .(week, list), nrow)
  sum$type <- 'sum'
  sum <- sum[c("week", "type", "list", "V1")]
  total <- ddply(relevant, .(week, type, list), nrow)
  total <- rbind(sum, total)
  colnames(total) <- c('week', 'type', 'list', 'patches')

  plot <- ggplot(total,
                 aes(x = week, y = patches, color = type)) +
    geom_line() +
    geom_smooth() +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    #scale_y_sqrt(breaks = c(10, 100, 250, 500, 1000, 2000, 3000, 4000, 5000)) +
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
  filename = paste('composition', plot_name, sep = '/')
  printplot(plot, filename, 4.5)
}

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
for (i in c('composition', 'ignored_total', 'ignored_absolute', 'ignored_fraction')) {
  dir.create(paste(d_dst, i, sep = '/'), showWarnings = FALSE)
}

if (!exists('raw_data')) {
  raw_data <- load_characteristics(f_characteristics)
}

if (!exists('releases')) {
  releases <- load_releases(f_releases)
}

# Filter strong outliers
filtered_data <- raw_data %>%
  filter(from != 'baolex.ni@intel.com') %>%
  filter(week < maxdate) %>%
  filter(week > mindate)

# Prepare data for project-global analysis. When we consider 'all' lists,
# we need to remove mails that were sent to multiple lists. As a consequence,
# we need to drop the list.matches_patch column, as this value is tied to
# the list information.
all <- filtered_data %>% select(-c(list.matches_patch))
all$list <- 'Overall'
all <- all %>% distinct()

# Calculate a list of all existing mailing lists
mailing_lists <- unique(filtered_data$list)

# Exemplarily, a selection of a set of mailing lists:
selection <- filtered_data %>%
  filter(list %in% c('linux-arm-kernel@lists.infradead.org',
                     'netdev@vger.kernel.org',
                     'linuxppc-dev@lists.ozlabs.org',
                     'alsa-devel@alsa-project.org'
                     ))

#ignored_by_week(selection)
#ignored_by_week(filtered_data)
ignored_by_week(all, 'overall')
composition(all, 'overall')
for (l in mailing_lists) {
  this_data = filtered_data %>% filter(list == l)
  ignored_by_week(this_data, l)
}

#ignore_rate_by_years(all)