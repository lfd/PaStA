#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Pia Eichinger <pia.eichinger@st.oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.
source("analyses/maintainers_graph_util.R")
library(dplyr)

# taken from website https://www.r-bloggers.com/2021/11/how-to-calculate-jaccard-similarity-in-r/
jaccard <- function(df_a, df_b, c_a, c_b) {
  df_a <- df_a[df_a$c_representative == c_a,]
  df_b <- df_b[df_b$c_representative == c_b,]

  intersection = length(intersect(df_a$c_section, df_b$c_section))
  union = length(df_a$c_section) + length(df_b$c_section) - intersection
  return (intersection/union)
}

#compare_clusters_adj_rand <- function(df_a, df_b, c_a, c_b) {
#  df_a <- df_a[df_a$c_representative == c_a,]
#  df_b <- df_b[df_b$c_representative == c_b,]
#
#  #intersection <- intersect(df_a$c_section, df_b$c_section)
#  #min_set_size <- min(nrow(df_a), nrow(df_b))
#  #intersect_coeff <- length(intersection)/min_set_size
#  # the higher, the better
#  rand_index <- adj.rand.index(df_a$c_section, df_b$c_section)
#
#  return(rand_index)
#}

data_dir_name <- file.path("resources", project, "resources/maintainers_cluster")
csv_dst <- file.path("resources", project, "resources/maintainers_cluster_similarity.csv")
other_dir_name <- file.path("resources", project, "resources/maintainers_cluster_louvain")

methods <- c("louvain", "infomap", "fast_greedy")

graphs <- list()
graphs_rest <- list()

files <- list.files(path = data_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
files <- files[!grepl("-rc", files, fixed = TRUE)]
files <- stringr::str_sort(files, numeric = TRUE)

c_version <- c()
c_clustering <- c()
c_representative <- c()
c_maxoverlap <- c()
c_max_representative <- c()
c_cluster_size <- c()

for (file_name in files) {
  print(paste0("Parsing file ", file_name, "..."))
  cluster_df <- read.csv(file_name)
  cluster_table <- table(cluster_df$c_representative)
  for (m in methods){
    other_dir_name <- paste(data_dir_name, m, sep = '_')
    other_file_name <- file.path(other_dir_name, basename(file_name))
    if (!file.exists(other_file_name)) {
       print(paste0(other_file_name, " does not exist for clustering method ", m))
       next
    }
    other_df <- read.csv(other_file_name)
    
    for (a in unique(cluster_df$c_representative)) {
      max <- 0
      max_rep <- NA
      for (b in unique(other_df$c_representative)) {
        overlap <- jaccard(cluster_df, other_df, a, b)
        if (overlap > max) {
          max <- overlap
          max_rep <- b
        }
      }
      c_version <- c(c_version, basename(file_name))
      c_clustering <- c(c_clustering, m)
      c_representative <- c(c_representative, a)
      c_maxoverlap <- c(c_maxoverlap, max)
      c_max_representative <- c(c_max_representative, max_rep)
      c_cluster_size <- c(c_cluster_size, unname(cluster_table[a]))
    }
  }
}

df <- data.frame(c_version, c_clustering, c_representative, c_maxoverlap, c_max_representative, c_cluster_size)
write.csv(df, csv_dst)

ggplot(df, aes(x = c_cluster_size, y = c_maxoverlap)) +
  facet_wrap(~ c_clustering) +
  geom_point(size = 2, alpha = 0.01, color="black") +
  geom_point(data = df %>% filter(c_representative == c_max_representative), color="#69b3a2", size=1, alpha = 0.1)

#for (file_name in files) {
#  file_map_name <- substr(basename(file_name), 1, nchar(basename(file_name))-4)
#  file_map_name <- paste0(file_map_name, "_filemap.csv")
#  file_map_name <- sub(basename(file_name), file_map_name, file_name)
#  
#  g_data <- maintainers_section_graph(file_name, project, file_map_name)
#  g <- g_data$graph
#  g$version <- basename(file_name)
#  graphs_rest[[length(graphs_rest)+1]] <- g
#}
#
#for (i in 1:length(files)) {
#  #print(i)
#  g <- graphs[[i]]
#  g_rest <- graphs_rest[[i]]
#  
#  wt_comm <- cluster_walktrap(g)
#  comm_groups <- igraph::groups(wt_comm)
#  wt_comm_rest <- cluster_walktrap(g_rest)
#  comm_groups_rest <- igraph::groups(wt_comm_rest)
#  len_comm <- length(comm_groups)
#  len_comm_rest <- length(comm_groups_rest)
#  
#  if(len_comm != len_comm_rest) {
#    print("NOT THE SAME AMOUNT BY")
#    print(len_comm - len_comm_rest)
#    #next
#  }
#  
#  print("HELLO?!?!?")
#  # test if it's still the same if we delete the vertex "THE REST" and then test the clusters
#  g_rest <- igraph::delete.vertices(g_rest, "THE REST")
#  for (j in 1:len_comm) {
#    #print(j)
#    group <- comm_groups[[j]]
#    memberships <- unname(membership(wt_comm)[group])
#    max_overlap <- max(table(memberships))
#    if (max_overlap != len_comm) {
#      print(paste0("Overlap for group ", str(j), " was ", str(max_overlap/length(group))))
#    }
#  }
#}
#
#file_name <- "resources/linux/resources/maintainers_section_graph/v5.15.csv"
#p <- "linux"
#file_map_name <- substr(basename(file_name), 1, nchar(basename(file_name))-4)
#file_map_name <- paste0(file_map_name, "_filemap.csv")
#file_map_name <- sub(basename(file_name), file_map_name, file_name)
#
#g_data <- maintainers_section_graph(p, file_name, file_map_name)
#g <- g_data$graph
#meta_g <- g_data$meta
#
#comm_groups <- g_data$comm_groups
#c_representative <- c()
#c_section <- c()
#c_size <- c()
#for (n in sort(V(meta_g)$name)) {
#  # get the index associated with the node in the meta graph
#  index <- V(meta_g)[n]$index
#  # the index will correlate to the list in comm_groups, which are
#  # its sections
#  sections <- unname(comm_groups[index])[[1]]
#  c_representative[(length(c_representative)+1):(length(c_representative)+length(sections))] <- n
#  c_section <- c(c_section, sections)
#  c_size <- c(c_size, V(g_data$g)[sections]$size)
#}
#df <- data.frame(c_representative, c_section, c_size)
#df <- df[order(c_representative, c_section),]
#write.table(df, dst, row.names=FALSE, sep = ",")
