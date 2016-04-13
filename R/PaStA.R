#!/usr/bin/env Rscript

library(tikzDevice)
library(ggplot2)
library(reshape2)
library(plyr)

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
          "#CC79A7")

# Y-m-d Date converter
convertDate <- function(table, columns) {
  table[, columns] <- as.data.frame(lapply(table[, columns, drop = FALSE],
                                           as.Date))
  return(table)
}

# Save as ggplot as tikz and png
savePlot <- function(filename, plot) {
  TEXWIDTH <- 5.87614
  tex_filename <- file.path(output_dir, paste(project_name, "-", filename, ".tex", sep = ""))
  png_filename <- file.path(output_dir, paste(project_name, "-", filename, ".png", sep = ""))
  
  tikz(tex_filename, standAlone = FALSE, width = 5, height = 5)
  print(plot)
  dev.off()

  png(png_filename)
  print(plot)
  dev.off()
}

# Read a CSV file
read_csv <- function(filename) {
  read.csv(filename,
           header=TRUE,
           sep=' ')
}

# The num_commit plot
num_commits <- function() {
  commitcount <- as.data.frame(table(patch_groups$StackVersion))
  colnames(commitcount) <- c("Version", "NumCommits")
  commitcount <- merge(x = commitcount,
                       y =  stack_release_dates,
                       by.x = "Version",
                       by.y = "Version")
  
  # some sugar
  commitcount <- commitcount[, c(3,1,4,2)]

  mindate <- min(commitcount$ReleaseDate)
  maxdate <- max(commitcount$ReleaseDate)

  vgs <- unique(commitcount$VersionGroup)
  vgs <- sort(vgs)

  xticks <- do.call("c", lapply(vgs, function(x)
    c(min(subset(commitcount, VersionGroup == x)$ReleaseDate)#,
      #max(subset(commitcount, VersionGroup == x)$ReleaseDate)
    )
  ))
  
  p <- ggplot(commitcount,
              aes(x = ReleaseDate,
                  y = NumCommits,
                  group = VersionGroup,
                  colour = VersionGroup)) +
    geom_line(size = 1.2) +
    ylim(200, max(commitcount$NumCommits)) +
    scale_x_date(date_labels = "%b %Y",
                 limits = c(mindate, maxdate),
                 breaks = xticks) +
    theme_bw(base_size = 15) +
    scale_color_manual(values = cols) +
    xlab("Timeline") + 
    ylab("Number of commits") +
    theme(legend.position = "top",
          legend.title = element_blank(),
          axis.line = element_line(),
          axis.text.x = element_text(angle = 65,
                                     hjust = 1))
  return(p)
}

# Upstream analysis
upstream_analysis <- function(binwidth) {
  upstream$DateDiff <- as.numeric(upstream$DateDiff, units="days")

  p <- ggplot(data = upstream,
             aes(upstream$DateDiff)) +
    xlab("Days between release and upstream") +
    ylab("Number of upstream patches") +
    geom_histogram(binwidth = binwidth)

  return(p)
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

  create_plot <- function(ver_grp) {
    observation <- subset(branch_observation, VersionGroup == ver_grp)
    plot <- ggplot(observation,
              aes(x = StackVersion, y = V1, fill = Type)) +
      geom_bar(stat = "identity") +
      xlab("Stack Version") +
      theme(legend.position = "right",
            axis.title.y = element_blank(),
            axis.text.x = element_text(angle = 90,
                                       hjust = 1)) +
      scale_fill_discrete(name = ver_grp)
    #guides(fill = guide_legend(title = x))
    return(list(ver_grp, plot))
  }

  results <- lapply(ord_version_grps, create_plot)
  return(results)
}


### Program start ###
args <- commandArgs(trailingOnly = TRUE)

if (length(args) == 0) {
  project_name <- "SAMPLE"
  output_dir <- "foo"

  release_sort_filename <- '/home/ralf/workspace/PaStA/foo/release-sort'
  mainline_release_dates_filename <- '/home/ralf/workspace/PaStA/foo/mainline-release-dates'
  stack_release_dates_filename <- '/home/ralf/workspace/PaStA/foo/stack-release-dates'
  patch_groups_filename <- '/home/ralf/workspace/PaStA/foo/patches'
  upstream_filename <- '/home/ralf/workspace/PaStA/foo/upstream'
  occurrence_filename <- '/home/ralf/workspace/PaStA/foo/patch-occurrence'

  persistent = FALSE
} else {
  project_name <- args[1]
  output_dir <- args[2]

  release_sort_filename <- args[3]
  mainline_release_dates_filename <- args[4]
  stack_release_dates_filename <- args[5]
  patch_groups_filename <- args[6]
  upstream_filename <- args[7]
  occurrence_filename <- args[8]

  persistent = TRUE
}

# Load all csv files
mainline_release_dates <- read_csv(mainline_release_dates_filename)
stack_release_dates <- read_csv(stack_release_dates_filename)
patch_groups <- read_csv(patch_groups_filename)
upstream <- read_csv(upstream_filename)
occurrence <- read_csv(occurrence_filename)
release_sort = read_csv(release_sort_filename)

# Convert columns containing dates
mainline_release_dates <- convertDate(mainline_release_dates,
                                      c("ReleaseDate"))
stack_release_dates <- convertDate(stack_release_dates,
                                   c("ReleaseDate"))
upstream <- convertDate(upstream, c("UpstreamCommitDate", "FirstStackOccurence"))

# Prepare Tables
upstream$DateDiff <- upstream$UpstreamCommitDate - upstream$FirstStackOccurence
upstream$Type <- sapply(upstream$DateDiff, function(x) {
  if (x < -1)
    "backport"
  else
    "forwardport"
})

# Set Version as ord. factors
ord_stack_ver = factor(unique(release_sort$Version),
                       ordered = TRUE,
                       levels = unique(release_sort$Version))

ord_version_grps = factor(unique(release_sort$VersionGroup),
                          ordered = TRUE,
                          levels = unique(release_sort$VersionGroup))

release_sort$VersionGroup <- factor(release_sort$VersionGroup,
                                    ordered = TRUE,
                                    levels = ord_stack_ver)

release_sort$Version <- factor(release_sort$Version,
                               ordered = TRUE,
                               levels = ord_stack_ver)

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

commitcount_plot <- num_commits()
upstream_analysis_plot <- upstream_analysis(7)
branch_observation_plots <- branch_observation()

if (persistent) {
  savePlot("commitcount", commitcount_plot)
  savePlot("upstream-analysis", upstream_analysis_plot)
  for (i in branch_observation_plots) {
    savePlot(paste("branch-observation-",
                   i[[1]],
                   sep = ""), i[[2]])
  }
} else {
  print(commitcount_plot)
  print(upstream_analysis_plot)
  for(i in branch_observation_plots) {
    print(i[[2]])
  }
}
