library(ggplot2)
library(lubridate)
library(dplyr)
library(plyr)
library(reshape2)
library(tikzDevice)

dst <- '/tmp/R'
dir.create(dst, showWarnings = FALSE)

load_csv <- function(filename) {
  data <- read.csv(filename, header = TRUE, sep=",")
  data$upstream <- as.logical(data$upstream)
  data$ignored <- as.logical(data$ignored)
  data$mtrs_correct <- as.logical(data$mtrs_correct)
  data <- data %>% mutate(date = as.Date(time))
  # Add week info
  data <- data %>% mutate(week = as.Date(cut(date, breaks = "week")))

  return(data)
}

if (!exists('raw_data')) {
  raw_data <- load_csv('characteristics.raw')
}

filtered_data <- raw_data

# Filter strong outliers
filtered_data <- filtered_data %>% filter(from != 'baolex.ni@intel.com')

filtered_data <- filtered_data %>% 
  filter(week > '2011-05-10')

fname <- function(file, extension) {
  return(file.path(dst, paste(file, extension, sep='')))
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
  
  relevant <- data %>% select(week, ignored)
  
  count_predicate <- function(data, row, value, name) {
    ret <- relevant %>% filter(UQ(as.name(row)) == value)
    ret <- ddply(ret, .(week), nrow)
    colnames(ret) <- c('week', name)
    return(ret)
  }
  
  true <- count_predicate(relevant, variable, TRUE, true_case)
  false <- count_predicate(relevant, variable, FALSE, false_case)
  
  total <- ddply(relevant, .(week), nrow)
  colnames(total) <- c('week', 'total')
  
  df <- merge(x = true, y = false, by = c('week'))
  df <- merge(x = df, y = total, by = c('week'))
  
  df$fraction <- df$ignored / df$total
  
  df <- melt(df, id.vars = c('week'))
  
    relevant <- df %>% filter(variable == true_case | variable == 'total')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm") +
    scale_y_log10() +
    ylab('Number of patches') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    theme_bw(base_size = 15) +
    # theme(legend.position = 'top') +
    labs(color = '')
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
    ylab('Total number of ignored patches') +
    ylim(c(0, 150)) +
    theme(legend.position = 'None')
  printplot(plot, 'ignored_by_week_ignored_only', 3)
                
  relevant <- df %>% filter(variable == 'fraction')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm", fill = 'green', colour = 'black') +
    geom_smooth(fill = 'blue', colour = 'black') +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
                       breaks = seq(0.01, 0.06, by = 0.01)) +
    xlab('Date') +
    ylab('Ratio of ignored patches') +
    #ylab('Ratio of correctly addressed maintainers') +
    theme(legend.position = 'None')
  printplot(plot, 'ignored_by_week_fraction', 3)
}

ignored_by_rc <- function(data) {
  data <- data %>% select('kv', 'rc', 'ignored')
  
  total <- ddply(data, .(kv, rc), nrow)
  colnames(total) <- c('kv', 'rc', 'total')
  
  ignored <- data %>% filter(ignored == TRUE)
  ignored <- ddply(ignored, .(kv, rc), nrow)
  colnames(ignored) <- c('kv', 'rc', 'ignored')
  
  df <- merge(x = total, y = ignored, by = c('kv', 'rc'))
  df$fraction <- df$ignored / df$total
  df <- melt(df, id.vars = c('kv', 'rc'))
  
  relevant <- df %>% filter(variable == 'fraction') %>% select(kv, rc, value)
  
  plot <- ggplot(relevant,
                 aes(x = rc, y = value, group = rc)) +
    geom_boxplot() +
    theme_bw(base_size =  15) +
    scale_x_continuous(breaks = 0:10,
                       labels = c('MW', 1:10)) +
    scale_y_continuous(labels = scales::percent_format(accuracy = 1, suffix = "\\%"),
                       breaks = seq(0.01, 0.06, by = 0.01)) +
    xlab('Development Stage (-rc)') +
    ylab('Probability that patch is ignored')
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

#ignore_rate_by_years(filtered_data)
#ignored_by_rc(raw_data)
ignored_by_rc(filtered_data)

#filtered_data$ignored <- filtered_data$mtrs_correct
#filtered_data <- filtered_data %>% filter(kv != 'v2.6.39')
#ignored_by_week(filtered_data)

#scatterplots(filtered_data)
#week_scatterplots(filtered_data)
