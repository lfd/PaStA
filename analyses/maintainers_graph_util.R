#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#   Pia Eichinger <pia.eichinger@st.oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

source("analyses/util.R")

library(igraph, warn.conflicts = FALSE)
library(RColorBrewer)

generate_cluster_matrix <- function(file_map, wt_comm, dimension) {
  # first calculate the edges between
  weight_matrix <- matrix(0, nrow = dimension, ncol = dimension)
  for (row in 1:nrow(file_map)) {
    # get distinct list of which clusters the sections of the file belong to
    sections <- file_map[row, 'sections']
    clusters <- unique(membership(wt_comm)[unlist(sections)])
    lines <- file_map[row, 'lines']

    for (i in 1:length(clusters)){
      first <- clusters[i]
      for (j in 1:length(clusters)) {
        second <- clusters[j]
        weight_matrix[first, second] = weight_matrix[first, second] + lines
       }
     }
  }

  return(weight_matrix)
}

# Test some stuff

library(ggraph)
maintainers_section_graph_ggraph <- function(project, file_name, file_map_name, clustering_method = "", sanitize = FALSE) {
  data_frame <- read_csv(file_name)
  file_map <- read.csv(file_map_name, header = TRUE)
  # solution taken from https://stackoverflow.com/questions/18893390/splitting-on-comma-outside-quotes
  file_map <- file_map %>% mutate(sections = stringr::str_split(sections, ',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)'))
  data_frame$weight <- data_frame$lines

  sanitize_routine <- function(p, r, row) {
     return(gsub(pattern=p, replace=r, row))
  }

  if(sanitize) {
    data_frame$from <- sanitize_routine("_", "-", data_frame$from)
    data_frame$to <- sanitize_routine("_", "-", data_frame$to)
    data_frame$from <- sanitize_routine("&", "AND", data_frame$from)
    data_frame$to <- sanitize_routine("&", "AND", data_frame$to)

    file_map$sections <- sanitize_routine("_", "-", file_map$sections)
    file_map$sections <- sanitize_routine("&", "AND", file_map$sections)
  }
  g  <- igraph::graph_from_data_frame(data_frame, directed = FALSE)
  
  # We need to remove THE REST because it's trivial that this section contains
  # everything. In case of QEMU, since this node is QEMU's equivalent of THE REST
  # whereas THE REST doesn't exist, we need to remove General Project
  # Administration instead
  section_the_rest <- "THE REST"
  if (project == 'qemu') {
    section_the_rest <- which(grepl("General Project Administration", V(g)$name))
  }
  g <- igraph::delete.vertices(g, section_the_rest)
  file_map$sections <- file_map$sections %>% lapply(function(x) substr(x, 2, nchar(x)-1)) %>%
    lapply(function(x) x[x != section_the_rest])

  # retrieve vertex size by finding edge weight of self loop
  for (e in which(which_loop(g))) {
    assertthat::are_equal(head_of(g, E(g)[e]), tail_of(g, E(g)[e]))
    my_vertex <- head_of(g, E(g)[e])
    edge_weight <- E(g)[e]$weight
    g <- igraph::set.vertex.attribute(g, "size", my_vertex, edge_weight)
  }
  
  quantile_step <- "50%"
  quantiles <- quantile(V(g)$size, c(.50, .80, .90, .95, .98, .99)) 
  communities <- cluster_infomap(g)
  V(g)$clu <- as.character(membership(communities))
  
  g_layout <- create_layout(g, layout = "dh")

  g_graph <- ggraph(g_layout) +
  geom_edge_link0(aes(edge_width = weight),edge_colour = "grey66")+
  geom_node_point(aes(fill = clu, size = size),shape = 21)+
  geom_node_text(aes(filter = size >= unname(quantiles[quantile_step]), label = name),family="serif", size=3)+
  #scale_edge_width(range = c(0.2,3))+
  #scale_size(range = c(1,6))+
  theme_graph(base_family = "Helvetica")+
  theme(legend.position = "none") +
  ggtitle("U-Boot Test")
  g_graph
}
# function to generate the maintainers_section_graph, its communities,
# its groups and bounds in a list in said order

maintainers_section_graph <- function(project, file_name, file_map_name, clustering_method = "", sanitize = FALSE) {
  data_frame <- read_csv(file_name)
  file_map <- read.csv(file_map_name, header = TRUE)
  # solution taken from https://stackoverflow.com/questions/18893390/splitting-on-comma-outside-quotes
  file_map <- file_map %>% mutate(sections = stringr::str_split(sections, ',(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)'))
  data_frame$weight <- data_frame$lines

  sanitize_routine <- function(p, r, row) {
     return(gsub(pattern=p, replace=r, row))
  }

  if(sanitize) {
    data_frame$from <- sanitize_routine("_", "-", data_frame$from)
    data_frame$to <- sanitize_routine("_", "-", data_frame$to)
    data_frame$from <- sanitize_routine("&", "AND", data_frame$from)
    data_frame$to <- sanitize_routine("&", "AND", data_frame$to)

    file_map$sections <- sanitize_routine("_", "-", file_map$sections)
    file_map$sections <- sanitize_routine("&", "AND", file_map$sections)
  }

  g  <- igraph::graph_from_data_frame(data_frame, directed = FALSE)

  # We need to remove THE REST because it's trivial that this section contains
  # everything. In case of QEMU, since this node is QEMU's equivalent of THE REST
  # whereas THE REST doesn't exist, we need to remove General Project
  # Administration instead
  section_the_rest <- "THE REST"
  if (project == 'qemu') {
    section_the_rest <- which(grepl("General Project Administration", V(g)$name))
  }
  g <- igraph::delete.vertices(g, section_the_rest)
  file_map$sections <- file_map$sections %>% lapply(function(x) substr(x, 2, nchar(x)-1)) %>%
    lapply(function(x) x[x != section_the_rest])

  # retrieve vertex size by finding edge weight of self loop
  for (e in which(which_loop(g))) {
    assertthat::are_equal(head_of(g, E(g)[e]), tail_of(g, E(g)[e]))
    my_vertex <- head_of(g, E(g)[e])
    edge_weight <- E(g)[e]$weight
    g <- igraph::set.vertex.attribute(g, "size", my_vertex, edge_weight)
  }

  # delete all self loops
  g <- igraph::simplify(g, remove.multiple = TRUE, remove.loops = TRUE)
  #if (project == 'linux') {
  #  g <- igraph::delete.vertices(g, V(g)[grepl("DRIVER", toupper(V(g)$name))])
  #}

  # get clustering
  ret_wt_comm <- cluster_walktrap(g)
  #ret_wt_comm <- cluster_louvain(g)
  #ret_wt_comm <- cluster_fast_greedy(g)
  #ret_wt_comm <- cluster_infomap(g)

  if (clustering_method == "_louvain") {
    ret_wt_comm <- cluster_louvain(g)
  } else if (clustering_method == "_infomap") {
    ret_wt_comm <- cluster_infomap(g)
  } else if (clustering_method == "_fast_greedy") {
    ret_wt_comm <- cluster_fast_greedy(g)
  }

  # get number of existing clusters within graph as bounds for processing
  ret_comm_groups <- igraph::groups(ret_wt_comm)
  ret_bounds <- seq(1, length(ret_comm_groups), 1)
  weight_matrix <- generate_cluster_matrix(file_map, ret_wt_comm, length(ret_bounds))
  meta_g <- make_empty_graph(directed = FALSE)
  for (i in ret_bounds) {
    group <- ret_comm_groups[i]
    group_list <- unname(group)[[1]]
    cluster_graph <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list)))
    maximum_name <- V(cluster_graph)$name[which.max(V(cluster_graph)$size)]
    # after extracting the maximum name, delete the vertex from the
    # intermediate cluster graph to extract the next maximum
    cluster_graph <- igraph::delete.vertices(cluster_graph, maximum_name)
    meta_g <- igraph::add.vertices(meta_g, 1, name = maximum_name,
                      index=i, size = weight_matrix[i, i])
  }
  for (i in ret_bounds) {
    for (j in ret_bounds) {
      if (j == i){
        next
      }
      if (weight_matrix[i, j] != 0) {
        meta_g <- igraph::add.edges(meta_g, c(i, j), weight = weight_matrix[i, j])
      }
    }
  }
  return(list(graph = g, wt_comm = ret_wt_comm, f_map = file_map,
              comm_groups = ret_comm_groups, bounds = ret_bounds, meta = meta_g))
}

write_cluster_csv <- function(g_data, dst) {
  meta_g <- g_data$meta
  comm_groups <- g_data$comm_groups

  c_representative <- c()
  c_section <- c()
  c_size <- c()

  for (n in sort(V(meta_g)$name)) {
    # get the index associated with the node in the meta graph
    index <- V(meta_g)[n]$index
    # the index will correlate to the list in comm_groups, which are
    # its sections
    sections <- unname(comm_groups[index])[[1]]

    c_representative[(length(c_representative)+1):(length(c_representative)+length(sections))] <- n
    c_section <- c(c_section, sections)
    c_size <- c(c_size, V(g_data$g)[sections]$size)
  }
  df <- data.frame(c_representative, c_section, c_size)
  df <- df[order(c_representative, c_section),]

  write.table(df, dst, row.names=FALSE, sep = ",", qmethod='double')
}

write_cluster_csv <- function(g_data, dst) {
  meta_g <- g_data$meta
  comm_groups <- g_data$comm_groups

  c_representative <- c()
  c_section <- c()
  c_size <- c()

  for (n in sort(V(meta_g)$name)) {
    # get the index associated with the node in the meta graph
    index <- V(meta_g)[n]$index
    # the index will correlate to the list in comm_groups, which are
    # its sections
    sections <- unname(comm_groups[index])[[1]]

    c_representative[(length(c_representative)+1):(length(c_representative)+length(sections))] <- n
    c_section <- c(c_section, sections)
    c_size <- c(c_size, V(g_data$g)[sections]$size)
  }
  df <- data.frame(c_representative, c_section, c_size)
  df <- df[order(c_representative, c_section),]

  write.table(df, dst, row.names=FALSE, sep = ",")
}

compare_cluster_csv <- function(df_a, df_b, c_a, c_b) {
  df_a <- df_a[df_a$c_representative == c_a,]
  df_b <- df_b[df_b$c_representative == c_b,]

  intersection <- intersect(df_a$c_section, df_b$c_section)
  min_set_size <- min(nrow(df_a), nrow(df_b))
  intersect_coeff <- length(intersection)/min_set_size

  return(intersect_coeff)
}
