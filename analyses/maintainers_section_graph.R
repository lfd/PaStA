#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2019-2020
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#   Pia Eichinger <pia.eichinger@st.oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

library("igraph")
library("RColorBrewer")
source("analyses/util.R")

# delete all vertices below this quantile
VERTEX_QUANTILE <- '80%'
# delete all edges below this quantile, also used for linder edge density layout
EDGE_QUANTILE <- '0%'

PALETTE <- c('#D83359','#979CFB','#f46d43','#fdae61','#fee090','#ffffbf','#e0f3f8','#abd9e9','#74add1','#4575b4','#d73027')

PRINT_ENTIRE_GRAPH <- TRUE
PRINT_CLUSTERS <- TRUE

VERTEX_SIZE <- 0.5
LABEL_SIZE <- 0.6

# minimum size of nodes in printed clusters
MIN_CLUSTERSIZE <- 20
# maximum size of nodes in printed clusters
MAX_CLUSTERSIZE <- 100
FONT_FAMILY <- "Helvetica"

PRINT_DEGREE_INFO <- FALSE
PRINT_INFORMATION <- FALSE
DISPLAY_LABELS <- FALSE

args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) {
  file_name <- 'resources/linux/resources/maintainers_section_graph.csv'
} else {
  file_name <- args[1]
}

data_frame <- read_csv(file_name)
data_frame$weight <- data_frame$lines

g  <- igraph::graph_from_data_frame(data_frame, directed = FALSE)
# removing this because it's trivial that the rest includes everything
g <- igraph::delete.vertices(g, "THE REST")

# retrieve vertex size by finding edge weight of self loop
for (e in which(which_loop(g))) {
  assertthat::are_equal(head_of(g, E(g)[e]), tail_of(g, E(g)[e]))
  my_vertex <- head_of(g, E(g)[e])
  edge_weight <- E(g)[e]$weight
  g <- igraph::set.vertex.attribute(g, "size", my_vertex, edge_weight)
}

# delete all self loops
g <- simplify(g, remove.multiple = TRUE, remove.loops = TRUE)

probes <- seq(0, 1, 0.05)

global_edge_quantiles <- quantile(E(g)$weight, probs=probes)
global_vertex_quantiles <- quantile(V(g)$size, probs=probes)

print_graph_information <- function(param) {
  print("Number of vertices:")
  print(length(V(g)))

  print("Average vertex size")
  print(mean(V(g)$size))

  print("Number of edges")
  print(length(E(g)))

  print("Average edge weight")
  print(mean(E(g)$weight))

  deg <- igraph::degree(param)
  deg <- sort(deg, decreasing = TRUE)

  if (!PRINT_DEGREE_INFO) {
    return()
  }

  print("Top 10 Sections with highest degree:")
  for (j in seq(1, 10, 1)) {
    print(deg[j])
  }

  deg <- sort(deg)

  print("All isolated sections:")
  i <- 1
  while(unname(deg[i]) == 0) {
    print(deg[i])
    i <- i+1
  }

  deg <- sort(deg)

  print("Average degree including isolates:")
  print(mean(deg))

  stats_graph <- igraph::delete.vertices(g, igraph::degree(param)==0)
  print("Average degree exluding isolates:")
  print(mean(igraph::degree(stats_graph)))
}

print_graph_information(g)

# deleting all vertices and edges that are below the specified quantile
g <- igraph::delete.vertices(g, which(V(g)$size <= unname(global_vertex_quantiles[VERTEX_QUANTILE])))
g <- igraph::delete.edges(g, which(E(g)$weight <= unname(global_edge_quantiles[EDGE_QUANTILE])))

wt_comm <- cluster_walktrap(g)
V(g)$comm <- membership(wt_comm)

# deleting all edges and adding new ones only within clusters
layout_with_cluster_edges <- function(param, attraction) {
  g_grouped <- param
  wt_comm <- cluster_walktrap(param)
  V(g_grouped)$comm <- membership(wt_comm)
  g_grouped <- igraph::delete.edges(g_grouped, E(g_grouped))

  iterate <- seq(1, length(V(g_grouped)), 1)
  for (i in iterate) {
    for (j in iterate) {
      if (i == j) {
        next
      }
      if (V(g_grouped)[i]$comm == V(g_grouped)[j]$comm) {
        g_grouped <- igraph::add.edges(g_grouped, c(i, j), weight=attraction)
      }
    }
  }

  return(layout.fruchterman.reingold(g_grouped, niter = 500))
}

if (PRINT_ENTIRE_GRAPH) {
  LO = layout_with_cluster_edges(g, 0.1)
  printplot(g, 'complete_graph_labels',
              mark.groups = igraph::groups(wt_comm),
              mark.col = PALETTE,
              vertex.size = VERTEX_SIZE,
              vertex.label.dist = 0.5,
              vertex.label.cex = LABEL_SIZE,
              vertex.label.family = FONT_FAMILY,
              layout = LO
              )

  printplot(g, 'complete_graph',
              mark.groups = igraph::groups(wt_comm),
              mark.col = PALETTE,
              vertex.size = VERTEX_SIZE,
              vertex.label = NA,
              layout = LO
              )
}

comm_groups <- igraph::groups(wt_comm)
bounds <- seq(1, length(comm_groups), 1)

if (PRINT_CLUSTERS) {
  # save each cluster community as own plot clustered again from within
  for (i in bounds) {
    group <- comm_groups[i]
    group_list <- unname(group)[[1]]

    if (!is.na(MIN_CLUSTERSIZE) && length(group_list) < MIN_CLUSTERSIZE) {
      next
    }

    if (!is.na(MAX_CLUSTERSIZE) && length(group_list) > MAX_CLUSTERSIZE) {
      next
    }
    print(paste0("ITERATION: ", toString(i)))

    #dplyr doesn't work that well in lambda-like functions such as which
    my_in <- function(vertex) {
      return(vertex %in% group_list)
    }

    cluster_graph <- igraph::delete_vertices(g, which(!my_in(V(g)$name)))
    if (PRINT_INFORMATION) {
      print_graph_information(cluster_graph)
    }

    wt_clusters <- cluster_walktrap(cluster_graph)
    print_graph_information(cluster_graph)

    printplot(cluster_graph, toString(i),
                mark.groups=igraph::groups(wt_clusters),
                mark.col = PALETTE,
                vertex.size=VERTEX_SIZE,
                vertex.label.family = FONT_FAMILY,
                vertex.label.dist=0.5,
                vertex.label.cex=LABEL_SIZE,
                layout = layout_with_cluster_edges(cluster_graph, 0.01)
                )
  }
}
