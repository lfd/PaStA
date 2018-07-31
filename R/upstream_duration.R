library(ggplot2)
library(tikzDevice)
library(lubridate)

RESULT = '/tmp/upstream-duration'
dst = '/tmp/R'

fname <- function(file, extension) {
  return(file.path(dst, paste(file, extension, sep="")))
}

printplot <- function(plot, filename) {
  print(plot)
  ggsave(fname(filename, '.pdf'), plot, dpi=300, width = 8, device="pdf")
  #tikz(fname(filename, '.tex'), width = 7.5, height = 5)
  #print(plot)
  #dev.off()
}

#upstream_duration_orig <- read.table(RESULT, header=TRUE, sep=' ')
binwidth <- 1
upstream_duration <- upstream_duration_orig

upstream_duration$integration <- as.Date(upstream_duration$integration, "%Y-%m-%d")
upstream_duration$first_submission <- as.Date(upstream_duration$first_submission, "%Y-%m-%d")
upstream_duration$last_submission <- as.Date(upstream_duration$last_submission, "%Y-%m-%d")

integration_distribution <- function(target, title) {
  # Filter for non-backports
  days <- target$dur
  days <- days[days > 0]
  days <- days[days < quantile(days, 0.998)]
  
  print(quantile(days, 0.99))
  
  d = data.frame(days)
  p <- ggplot(d, aes(d$days)) +
    stat_ecdf(geom = "step", pad = FALSE) +
    scale_y_continuous(breaks=seq(0, 1, 0.05)) +
    scale_x_continuous(breaks=seq(0, 6000, 50)) +
    labs(x = "Integration duration in days", y = "Amount of patches being accepted within x days") +
    theme_bw() +
    ggtitle(title) +
    xlim(0, 1000) +
    geom_vline(xintercept = quantile(days, 0.99),
               colour = "red") +
    geom_vline(xintercept = quantile(days, 0.80),
               colour = "red") +
    geom_vline(xintercept = quantile(days, 0.70),
               colour = "red") +
    geom_vline(xintercept = quantile(days, 0.50),
               colour = "red")
  
  printplot(p, paste('upstream_duration', title, sep='-'))
  
  #q <- ggplot(d, aes(d$days)) +
  #  theme_bw(base_size = 15) +
  #  theme(axis.line = element_line()) +
  #  geom_histogram(binwidth = binwidth) +
  #  geom_vline(xintercept = 0, size=0.1,
  #             colour = "red")
}

integration_distribution(upstream_duration, "Overall")

start <- "2005-01-01"
end <- "2005-12-31"

for (i in 1:14) {
  start <- as.Date(start, "%Y-%m-%d")
  end <- as.Date(end, "%Y-%m-%d")

  window <- upstream_duration[upstream_duration$integration >= start &
                              upstream_duration$integration <= end,]

  integration_distribution(window, start)
  
  start <- start %m+% years(1)
  end <- end %m+% years(1)
}
