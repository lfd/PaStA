#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2019-2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

source("analyses/util.R")

date.min <- '2011-07-21' # v3.0
date.max <- '2020-12-13' # v5.10
top_n.num_lists <- 4
prj_releases <- paste(project, "Releases")

load_characteristics <- function(filename) {
  data <- read_csv(filename)
  data$list.matches_patch <- as.logical(data$list.matches_patch)
  data$ignored <- as.logical(data$ignored)
  data$committer.correct <- as.logical(data$committer.correct)
  data <- data %>% mutate(date = as.Date(time))

  # Add week info
  data <- data %>% mutate(week = as.Date(cut(date, breaks = "week")))

  return(data)
}

load_releases <- function(filename) {
  data <- read_csv(filename)
  data <- data %>% mutate(date = as.Date(date))
}

yearpp <- function(date) {
  ymd(paste0((year(date) + 1), '0101'))
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

ignored_by_week <- function(data, plot_name) {
  relevant <- data %>% select(week, ignored, list)

  true <- relevant %>% filter(ignored == TRUE) %>% select(-ignored) %>% group_by(week, list) %>% count(name = 'ignored')
  false <- relevant %>% filter(ignored == FALSE) %>% select(-ignored) %>% group_by(week, list) %>% count(name = 'not_ignored')
  total <- relevant %>% select(week, list) %>% group_by(week, list) %>% count(name = 'total')

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
  relevant <- df %>% filter(variable == 'ignored' | variable == 'total')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth() +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    scale_y_sqrt(breaks = c(10, 100, 250, 500, 1000, 2000, 3000, 4000, 5000)) +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name = prj_releases,
                                     breaks = releases$date,
                                     labels = releases$release)
                 ) +
    labs(color = '') +
    facet_wrap(~list, scales = 'free') +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 45, hjust = 0))
  filename <- file.path('ignored_total', plot_name)
  printplot(plot, filename)

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
                 sec.axis = dup_axis(name = prj_releases,
                                     breaks = releases$date,
                                     labels = releases$release)) +
    xlab('Date') +
    ylab('Total number of ignored patches per week') +
    facet_wrap(~list, scales = 'free') +
    my.theme +
    theme(legend.position = 'None',
          axis.text.x.top = element_text(angle = 45, hjust = 0))
  filename <- file.path('ignored_absolute', plot_name)
  printplot(plot, filename)

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
                 sec.axis = dup_axis(name = prj_releases,
                                     breaks = releases$date,
                                     labels = releases$release)) +
    #scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
    #                   breaks = seq(0.01, 0.06, by = 0.01)) +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%")) +
    xlab('Date') +
    ylab('Ratio of ignored patches') +
    facet_wrap(~list, scales = 'free') +
    my.theme +
    theme(legend.position = 'None',
          axis.text.x.top = element_text(angle = 45, hjust = 0))
  filename <- file.path('ignored_fraction', plot_name)
  printplot(plot, filename)
}

composition <- function(data, plot_name) {
  relevant <- data %>% select(week, type, list)

  total <- relevant %>%
    group_by(week, type, list) %>%
    count(list, name = 'num')
  sum <- total %>%
    group_by(week, list) %>%
    summarise(num = sum(num)) %>%
    mutate(type = 'sum', .before = 'list')
  total <- bind_rows(total, sum)

  plot <- ggplot(total,
                 aes(x = week, y = num, color = type)) +
    geom_line() +
    geom_smooth() +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    #scale_y_sqrt(breaks = c(10, 100, 250, 500, 1000, 2000, 3000, 4000, 5000)) +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name = prj_releases,
                                     breaks = releases$date,
                                     labels = releases$release)
    ) +
    labs(color = '') +
    facet_wrap(~list, scales = 'free') +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 45, hjust = 0))
  filename <- file.path('composition', plot_name)
  printplot(plot, filename)
}

patch_conform_by_week <- function(data, plot_name) {
  data <- top_n.list_data

  relevant <- data %>% select(week, committer.correct, list)

  true <- relevant %>% filter(committer.correct == TRUE) %>% select(-committer.correct) %>% group_by(week, list) %>% count(name = 'correct')
  false <- relevant %>% filter(committer.correct == FALSE) %>% select(-committer.correct) %>% group_by(week, list) %>% count(name = 'incorrect')
  not_integrated <- relevant %>% filter(is.na(committer.correct)) %>% select(-committer.correct) %>% group_by(week, list) %>% count(name = 'not_integrated')
  total <- relevant %>% select(week, list) %>% group_by(week, list) %>% count(name = 'total')

  # Fill up weeks with no values with zeroes
  total <- total %>% group_by(list) %>% group_modify(fillup_missing_weeks)

  # We must also merge weeks with no ignored patches, so all.x/y = TRUE
  df <- merge(x = true, y = false, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = not_integrated, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  df <- merge(x = df, y = total, by = c('week', 'list'), all.x = TRUE, all.y = TRUE)
  # Then, replace NA by 0
  df[is.na(df)] <- 0

  df <- melt(df, id.vars = c('week', 'list'))

  p <- ggplot(df, aes(x = week, y = value, color = variable)) +
    #geom_line() +
    geom_smooth() +
    geom_vline(xintercept = releases$date, linetype="dotted") +
    ylab('Number of patches per week') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 sec.axis = dup_axis(name = prj_releases,
                                     breaks = releases$date,
                                     labels = releases$release)
    ) +
    facet_wrap(~list, scales = 'free') +
    my.theme +
    theme(axis.text.x.top = element_text(angle = 90, hjust = 0),
          legend.title = element_blank())
  filename <- file.path('conform', plot_name)
  printplot(p, filename)
}

patch_conform_analysis <- function(data, plot_name) {
  # Filter for relevant patches written by humans (i.e., no bots, no stable-review, ...)
  commit_data <- data %>% select(list, committer.correct)
  
  # Uncomment this line to exclude not-integrated patches
  commit_data <- commit_data %>% filter(!is.na(committer.correct))

  # Remove TLDs
  commit_data$list <- sapply(strsplit(commit_data$list, '@'), '[', 1)

  commit_data <- commit_data %>% group_by(list)

  list_data <- commit_data %>%
    count(committer.correct, name = 'freq') %>%
    mutate(proportion = freq / sum(freq))

  sum <- commit_data %>%
    count(name = 'freq') %>%
    mutate(committer.correct = 'Sum', proportion = 1.0, .before = freq)

  top <- sum %>%
    select(list, freq) %>%
    group_by(list) %>%
    arrange(desc(freq))

  tmp <- list_data %>% mutate(committer.correct = as.character(committer.correct))
  sum <- bind_rows(tmp, sum) %>% ungroup()

  cat("ignored rates for: ", plot_name, "\n")
  cat("list; correct; incorrect; sum patches\n")
  for (l in top$list) {
    lst <- sum %>% filter(list == l) %>% select(-list)

    false <- (lst %>% filter(committer.correct == FALSE))$proportion
    true <- (lst %>% filter(committer.correct == TRUE))$proportion
    all <- (lst %>% filter(committer.correct == 'Sum'))$freq

    cat(sprintf("%s; %.2f; %.2f; %d\n", l, true, false, all))
  }
  
  p <- ggplot(list_data, aes(x=committer.correct, y = proportion)) +
    geom_bar(stat = 'identity', width = 0.5) +
    scale_x_discrete(breaks = c(FALSE, TRUE, NA),
                     labels = c('No', 'Yes', 'N.I.')) +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
                       limits = c(0, 1)) +
    facet_wrap(~list, nrow=3) +
    my.theme +
    theme(axis.title.x=element_blank(),
          axis.title.y=element_blank())
  filename <- file.path('conform', plot_name)
  printplot(p, filename)
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) {
  f_characteristics <- file.path(d_resources, 'characteristics.csv')
  f_releases <- file.path(d_resources, 'releases.csv')
} else {
  d_dst <- args[1]
  f_characteristics <- args[2]
  f_releases <- args[3]
}

create_dstdir(c('composition', 'conform', 'ignored_total', 'ignored_absolute', 'ignored_fraction'))

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

# Calculate the top-n lists with highest patch traffic. Note that we are only
# interested in high-traffic lists, so filter for the type 'patch'
top_n.data <- filtered_data %>%
  filter(type == 'patch') %>%
  select(list) %>%
  count(list, name = 'sum_patches') %>%
  slice_max(sum_patches, n = top_n.num_lists)
top_n.lists = top_n.data$list

# Plot the composition, before we filter drop everything but patches
composition(filtered_data %>% filter(list %in% top_n.lists), 'composition.top_n')

# Plot the composition for the whole project
all <- filtered_data %>% select(-c(list.matches_patch))
all$list <- 'Overall'
all <- all %>% distinct()
composition(all, 'composition.overall')

# Once the composition is plotted, we can limit on the type 'patch'. For the
# ignored patches analysis, we're only interested in patches that patch the project,
# and were written by real humans.
filtered_data <- filtered_data %>%
  filter(type == 'patch') %>%
  select(-type)

# Again, give a project-global overview. Simply merge all lists, and remove
# duplicates.
all <- filtered_data %>% select(-c(list.matches_patch))
all$list <- 'Overall'
all <- all %>% distinct()
ignore_rate_by_years(all)
ignored_by_week(all, 'ignored.overall')

# Create plots for the top-n lists
top_n.list_data <- filtered_data %>% filter(list %in% top_n.lists)
ignored_by_week(top_n.list_data, 'top_n')

# Create plots for conform integration
patch_conform_analysis(top_n.list_data, 'conform.top_n')
patch_conform_analysis(filtered_data, 'conform.all')
patch_conform_analysis(all, 'conform.overall')

patch_conform_by_week(top_n.list_data, 'conform.week.top_n')
