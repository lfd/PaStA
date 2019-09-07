library(ggplot2)
library(dplyr)
library(plyr)
library(reshape2)
library(tikzDevice)

dst <- '/tmp/R'

#raw_data <- read.csv('raw_data.csv', header = TRUE, sep=",")
#raw_data$upstream <- as.logical(raw_data$upstream)
#raw_data$ignored <- as.logical(raw_data$ignored)
#raw_data <- raw_data %>% mutate(date = as.Date(time))
# Add week info
#raw_data <- raw_data %>% mutate(week = as.Date(cut(date, breaks = "week")))

filtered_data <- raw_data

# Filter strong outliers
#filtered_data <- filtered_data %>% filter(from != 'baolex.ni@intel.com')

filtered_data <- filtered_data %>% 
  filter(week > '2011-05-10')

fname <- function(file, extension) {
  return(file.path(dst, paste(file, extension, sep='')))
}

printplot <- function(plot, filename) {
  print(plot)
  ggsave(fname(filename, '.pdf'), plot, dpi = 300, width = 8, device = 'pdf')
  
  tikz(fname(filename, '.tex'), width = 6.3, height = 5)
  print(plot)
  dev.off()
}

ignored_by_week <- function(data) {
  relevant <- data %>% select(week, ignored)
  
  ignored <- relevant %>% filter(ignored == TRUE)
  ignored <- ddply(ignored, .(week), nrow)
  colnames(ignored) <- c('week', 'ignored')
  
  not_ignored <- relevant %>% filter(ignored == FALSE)
  not_ignored <- ddply(not_ignored, .(week), nrow)
  colnames(not_ignored) <- c('week', 'not_ignored')
  
  total <- ddply(relevant, .(week), nrow)
  colnames(total) <- c('week', 'total')
  
  df <- merge(x = ignored, y = not_ignored, by = c('week'))
  df <- merge(x = df, y = total, by = c('week'))
  
  df$fraction <- df$ignored / df$total
  
  df <- melt(df, id.vars = c('week'))
  
  relevant <- df %>% filter(variable == 'ignored' | variable == 'total')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm") +
    scale_y_log10() +
    ylab('Numbers of patches') +
    xlab('Date') +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    theme_bw(base_size = 15) +
    theme(legend.position = 'top')
    labs(color = '')
  printplot(plot, 'ignored_by_week_total')
  
  
  relevant <- df %>% filter(variable == 'ignored') #%>% select(week, value)
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm") +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    xlab('Date') +
    ylab('total number of ignored patches') +
    scale_y_log10() +
    theme(legend.position = 'None')
  printplot(plot, 'ignored_by_week_ignored_only')
  
  relevant <- df %>% filter(variable == 'fraction')
  plot <- ggplot(relevant,
                 aes(x = week, y = value, color = variable)) +
    geom_line() +
    geom_smooth(method = "lm") +
    theme_bw(base_size = 15) +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y') +
    xlab('Date') +
    ylab('Ratio of ignored patches') +
    theme(legend.position = 'None')
  printplot(plot, 'ignored_by_week_fraction')
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
    scale_x_continuous(breaks = c(0,1,2,3,4,5,6,7,8,9,10)) +
    xlab('Development Stage (-rc)') +
    ylab('Probability that patch is ignored')
    printplot(plot, 'ignored_by_rc')
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
  plot <- ggplot(relevant, aes(x = total, y = ignored)) +
    geom_point() + geom_density2d()
  printplot(plot, 'foo5')
  
  relevant <- df %>% filter(total < 101)
  plot <- ggplot(relevant, aes(x = total, y = ignored)) +
    geom_point() + geom_density2d()
  printplot(plot, 'foo6')
  
  relevant <- df %>% filter(total < 101)
  plot <- ggplot(relevant, aes(x = total, y = ratio)) +
    geom_point() + geom_density2d()
  printplot(plot, 'foo7')
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
  printplot(plot, 'ignored_week_scatter')
}

#ignored_by_rc(raw_data)
#ignored_by_rc(filtered_data)
#ignored_by_week(filtered_data)
#scatterplots(filtered_data)
#week_scatterplots(filtered_data)