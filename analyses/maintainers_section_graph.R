#!/usr/bin/env Rscript

# PaStA - Patch Stack Analysis
#
# Copyright (c) OTH Regensburg, 2019-2021
#
# Author:
#   Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
#   Pia Eichinger <pia.eichinger@st.oth-regensburg.de>
#
# This work is licensed under the terms of the GNU GPL, version 2.  See
# the COPYING file in the top-level directory.

source("analyses/util.R")
source("analyses/maintainers_graph_util.R")

PALETTE <- c('#D83359','#979CFB','#f46d43','#fdae61','#fee090','#ffffbf','#e0f3f8','#abd9e9','#74add1','#4575b4','#d73027')

PRINT_ENTIRE_GRAPH <- FALSE
PRINT_CLUSTERS <- FALSE

VERTEX_SIZE <- 0.5
LABEL_SIZE <- 0.6

# maximum size of nodes in printed clusters
MAX_CLUSTERSIZE <- 100
FONT_FAMILY <- "Helvetica"

# minimum size of nodes in printed clusters
if (project == 'linux') {
  MIN_CLUSTERSIZE <- 8
} else if (project == 'qemu') {
  MIN_CLUSTERSIZE <- 5
} else {
  MIN_CLUSTERSIZE <- 4
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) {
  version <- 'HEAD'
} else {
  version <- args[1]
}

d_dst <- file.path(d_maintainers_cluster_img, version)
f_section_graph <- file.path(d_maintainers_section, paste(version, 'csv', sep='.'))
f_file_map <- file.path(d_maintainers_section, paste0(version, '_filemap', '.csv'))

if ("--print-entire-graph" %in% args) {
	PRINT_ENTIRE_GRAPH <- TRUE
}

if ("--print-clusters" %in% args) {
	PRINT_CLUSTERS <- TRUE
}

create_dstdir(c())

dir.create(d_maintainers_cluster, showWarnings = FALSE)
CLUSTER_DESTINATION <- file.path(d_maintainers_cluster, paste(version, 'csv', sep='.'))

graph_list <- maintainers_section_graph(project, f_section_graph, f_file_map)
g <- graph_list$graph
wt_comm <- graph_list$wt_comm
comm_groups <- graph_list$comm_groups
bounds <- graph_list$bounds

# assign community attribute based on walktrap clustering
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

    cluster_graph <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list)))

    wt_clusters <- cluster_walktrap(cluster_graph)

    printplot(cluster_graph, paste0("cluster_", toString(i)),
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

write_cluster_csv(graph_list, CLUSTER_DESTINATION)
