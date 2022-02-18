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

library(igraph, warn.conflicts = FALSE)
library(RColorBrewer)


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

file_name <- file.path(d_maintainers_section, paste(version, 'csv', sep='.'))

if ("--print-entire-graph" %in% args) {
	PRINT_ENTIRE_GRAPH <- TRUE
}

if ("--print-clusters" %in% args) {
	PRINT_CLUSTERS <- TRUE
}

d_maintainers_cluster <- file.path(d_resources, 'maintainers_cluster')
dir.create(d_maintainers_cluster, showWarnings = FALSE)
CLUSTER_DESTINATION <- file.path(d_maintainers_cluster,
                                 gsub(".csv$", ".txt", basename(file_name)))

data_frame <- read_csv(file_name)
data_frame$weight <- data_frame$lines

g  <- igraph::graph_from_data_frame(data_frame, directed = FALSE)

# We need to remove THE REST because it's trivial that this section contains
# everything. In case of QEMU, since this node is QEMU's equivalent of THE REST
# whereas THE REST doesn't exist, we need to remove General Project
# Administration instead
if (project == 'qemu') {
  g <- igraph::delete.vertices(g, which(grepl("General Project Administration",
                                            V(g)$name)))
} else {
  g <- igraph::delete.vertices(g, "THE REST")
}

# retrieve vertex size by finding edge weight of self loop
for (e in which(which_loop(g))) {
  assertthat::are_equal(head_of(g, E(g)[e]), tail_of(g, E(g)[e]))
  my_vertex <- head_of(g, E(g)[e])
  edge_weight <- E(g)[e]$weight
  g <- igraph::set.vertex.attribute(g, "size", my_vertex, edge_weight)
}

# delete all self loops
g <- simplify(g, remove.multiple = TRUE, remove.loops = TRUE)


# in case of Linux delete all entries with DRIVER
#if (project == 'linux') {
#  g <- igraph::delete.vertices(g, V(g)[grepl("DRIVER", toupper(V(g)$name))])
#}

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

    cluster_graph <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list)))

    wt_clusters <- cluster_walktrap(cluster_graph)

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

write_cluster_file <- function(g, dst) {
  for (name in names(comm_groups)) {
    comm_groups[[name]] <- sort(comm_groups[[name]])
  }
  sorted_comm_groups <- comm_groups[order(sapply(comm_groups,function(x) x[[1]]))]
  sink(dst)

  for (i in bounds) {
    group <- sorted_comm_groups[i]
    group_list <- unname(group)[[1]]

    for (section in group_list) {
      cat(section)
      cat('\n')
    }
    cat('\n')
  }
  sink()
}

write_cluster_file(g, CLUSTER_DESTINATION)
