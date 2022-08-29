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
NETWORK_SIZE <- 2
#NETWORK_SIZE <- 1

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

clustering_method <- ""

if ("--print-entire-graph" %in% args) {
	PRINT_ENTIRE_GRAPH <- TRUE
}

if ("--print-clusters" %in% args) {
	PRINT_CLUSTERS <- TRUE
}

if ("--louvain" %in% args) {
	clustering_method <- "_louvain"
}

if ("--infomap" %in% args) {
	clustering_method <- "_infomap"
}

if ("--fast_greedy" %in% args) {
	clustering_method <- "_fast_greedy"
}

create_dstdir(c())

d_maintainers_cluster <- paste0(d_maintainers_cluster, clustering_method)
dir.create(d_maintainers_cluster, showWarnings = FALSE)
CLUSTER_DESTINATION <- file.path(d_maintainers_cluster, paste(version, 'csv', sep='.'))

graph_list <- maintainers_section_graph(project, f_section_graph, f_file_map, clustering_method)
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

  Isolated = which(degree(g)==0)
  #TODO: das iwie rechtfertigen, weil es schaut hald echt schlecht aus
  g = delete.vertices(g, Isolated)

  V(g)$clu <- as.character(membership(cluster_walktrap(g)))
  quantile_step <- "75%"
  quantiles <- quantile(V(g)$size, c(.75, .80, .85, .90, .95, .98, .99)) 
  p <- ggraph(g, layout = "dh") +
  geom_edge_link0(aes(edge_width = weight),edge_colour = "grey66")+
  #geom_node_point(aes(fill = clu,size = size),shape = 21)+
  geom_node_point(aes(fill = clu, size = size),shape = 21)+
  geom_node_text(aes(filter = size >= unname(quantiles[quantile_step]), label = name),family="serif", size=2)+
  #geom_node_text(aes(label = name),family="serif", size=2)+
  #scale_fill_manual(values = got_palette)+
  scale_edge_width(range = c(0.2,3))+
  scale_size(range = c(1,6))+
  theme_graph(base_family = "Helvetica")+
  theme(legend.position = "none")
  #ggtitle(project)
  
  printplot(p, "microview")
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
    V(cluster_graph)$category <- sample(LETTERS, length(V(cluster_graph)), T)
    cluster_graph <- ggraph(cluster_graph, layout = "dh") +
    geom_edge_link0(aes(edge_width = weight),edge_colour = "grey66")+
    #geom_node_point(aes(fill = clu,size = size),shape = 21)+
    geom_node_point(aes(fill = category, size = size),shape = 21)+
    #geom_node_text(aes(filter = size >= unname(quantiles[quantile_step]), label = name),family="serif", size=4)+
    geom_node_text(aes(label = name),family="serif", size=NETWORK_SIZE, repel=TRUE)+
    #scale_fill_manual(values = got_palette)+
    scale_edge_width(range = c(0.2,3))+
    scale_size(range = c(1,6))+
    theme_graph(base_family = "Helvetica")+
    theme(legend.position = "none")
    #ggtitle(graph_name)

    #wt_clusters <- cluster_walktrap(cluster_graph)

    printplot(cluster_graph, paste0("cluster_", toString(i)))
  }
}

write_cluster_csv(graph_list, CLUSTER_DESTINATION)



#for (i in bounds) {
#group_1 <- comm_groups[indexes[1]]
#group_list_1 <- unname(group_1)[[1]]
#cluster_graph_1 <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list_1)))
#V(cluster_graph_1)$category <- sample(LETTERS, length(V(cluster_graph_1)), T)
#  
#}
#
#indexes <- c(25, 58)
#g <- graph_list$g
#comm_groups <- graph_list$comm_groups
#
#group_1 <- comm_groups[indexes[1]]
#group_list_1 <- unname(group_1)[[1]]
#cluster_graph_1 <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list_1)))
#V(cluster_graph_1)$category <- sample(LETTERS, length(V(cluster_graph_1)), T)
#
#group_2 <- comm_groups[indexes[2]]
#group_list_2 <- unname(group_2)[[1]]
#cluster_graph_2 <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list_2)))
#V(cluster_graph_2)$category <- sample(LETTERS, length(V(cluster_graph_2)), T)
#V(cluster_graph_2)$clu <- "black"
#
#
#ggraph(cluster_graph_1, layout = "dh") +
#geom_edge_link0(aes(edge_width = weight),edge_colour = "grey66")+
##geom_node_point(aes(fill = clu,size = size),shape = 21)+
#geom_node_point(aes(fill = category, size = size),shape = 21)+
##geom_node_text(aes(filter = size >= unname(quantiles[quantile_step]), label = name),family="serif", size=4)+
#geom_node_text(aes(label = name),family="serif", size=4, repel=TRUE)+
##scale_fill_manual(values = got_palette)+
#scale_edge_width(range = c(0.2,3))+
#scale_size(range = c(1,6))+
#theme_graph(base_family = "Helvetica")+
#theme(legend.position = "none")
##ggtitle(graph_name)
#
## TODO: make it reproducible to extract security subsystem
#filename <- file.path("resources/R", "security_subsystem")
#WIDTH <- 4
#HEIGHT <- 3
#tikz(paste0(filename, '.tex'), width = WIDTH, height = HEIGHT, sanitize=TRUE, standAlone = FALSE)
#
#ggraph(cluster_graph_2, layout = "stress") +
##geom_edge_link0(aes(edge_width = 0.25),edge_colour = "grey66")+
#geom_edge_link0(aes(edge_width = weight),edge_colour = "grey66")+
##geom_node_point(aes(fill = "black",size = size, colour="black"),shape = 21, color="black")+
##geom_node_point(aes(size=0.5, fill="white"))+
##geom_node_point(aes(fill = "black", size = size),shape = 21)+
##geom_node_text(aes(filter = size >= unname(quantiles[quantile_step]), label = name),family="serif", size=4)+
##geom_node_text(aes(label = name),family="serif", size=2.75, repel=FALSE)+
#geom_label(aes(x = x, y = y, label = name), nudge_y = 0, label.size = NA) +
##scale_fill_manual(values = got_palette)+
##scale_edge_width(range = c(0.2,3))+
#scale_edge_width(range = c(1.2,3))+
#scale_size(range = c(1,3))+
#theme_graph(base_family = "Helvetica")+
#  ylim(-1.5, 1.5) +
#  xlim(-1.5, 1.5) +
#theme(legend.position = "none")
##ggtitle(graph_name)
#dev.off()
#  
#  