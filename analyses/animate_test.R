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

library(ggraph)
library(igraph)
#library(gganimate)
library(graphlayouts)
#library(patchwork)
library(RColorBrewer)

source("analyses/mtr_sctn_graph_util.R")
# TODO: delete and sort out old comments and work, sort work
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) {
  data_dir_name <- file.path("resources", project, "resources/maintainers_section_graph")
  d_dst <- file.path("resources", project, "resources/maintainers_daumenkino")
} else {
  data_dir_name <- args[1]
  d_dst <- args[2]
}
dir.create(d_dst, showWarnings = FALSE, recursive = TRUE)

files <- list.files(path = data_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
files <- files[!grepl("-rc", files, fixed = TRUE)]
files <- files[!grepl("filemap", files, fixed = TRUE)]
files <- stringr::str_sort(files, numeric = TRUE)
# the first 17 versions of qemu do not contain any edges between clusters. We don't need to look at those
if (project == "qemu") {
  files <- files[18:79]
}

graphs <- list()

#g_v1 is the previous graph, g_v2 is the follower. node_name is ONE node of g_v2
find_largest_predecessor <- function(g_v1, g_v2, node_name) {
  version1 <- g_v1$version
  version2 <- g_v2$version

  version1_file_name <-
    file.path("resources", project, "resources/maintainers_cluster", version1)
  version2_file_name <-
    file.path("resources", project, "resources/maintainers_cluster", version2)

  df_1 <- read.csv(version1_file_name)
  df_2 <- read.csv(version2_file_name)

  # calculate cluster overlap for every single name in previous version, get
  # the max overlap
  max <- which.max(sapply(V(g_v1)$name,
                          function(x) compare_cluster_csv(df_1, df_2, x, node_name)))
  df_2 <- df_2[df_2$c_representative == node_name,]
  max_name <- names(max)
  # case 1: sapply returns a named array, e.g. 'ARM PORT': 3. We are only interested
  # in the given name, if > 0, since 0 would mean a 0 overlap
  # case 2: if the previous name (max) is not the same as the next one (node_name), we
  # have to determine if max is still within the cluster, therefore having a
  # change of representative. Otherwise, the
  # clusters have diverted and we need to assign a new value to node_name, therefore
  # giving it NA as predecessor, which will result in keeping the original colour
  condition_cluster_diverted <- (max_name != node_name ) && !(max_name %in% df_2$c_section)
  if ((unname(max) == 0) || condition_cluster_diverted) {
    max <- NA
  } else {
    max <- max_name
  }

  return(max)
}

for (file_name in files) {
  file_map_name <- substr(basename(file_name), 1, nchar(basename(file_name))-4)
  file_map_name <- paste0(file_map_name, "_filemap.csv")
  file_map_name <- sub(basename(file_name), file_map_name, file_name)
  
  g_data <- maintainers_section_graph(file_name, project, file_map_name)
  g <- g_data$meta
  g$version <- basename(file_name)
  graphs[[length(graphs)+1]] <- g
}

qual_col_pals = brewer.pal.info[brewer.pal.info$category == 'qual',]
col_vector = unlist(mapply(brewer.pal, qual_col_pals$maxcolors, rownames(qual_col_pals)))
palette_index <- 1
graph_palette <- list()
pList <- vector("list", length(graphs))
lList <- vector("list", length(graphs))

for (i in 1:length(graphs)) {
  #print(i)
  g <- graphs[[i]]
  Isolated = which(degree(g)==0)
  #TODO: das iwie rechtfertigen, weil es schaut hald echt schlecht aus
  g = delete.vertices(g, Isolated)
  
  quantile_step <- "95%"
  quantiles <- quantile(V(g)$size, c(.90, .95, .98, .99)) 
  communities <- cluster_louvain(g)
  V(g)$clu <- as.character(membership(communities))
  #V(g)$col <- unname(sapply(V(g)$clu, function(x) test[as.numeric(x)]))
  # TODO: something better?
  V(g)$col <- "black"

  graphs[[i]] <- g

  ## Every community of nodes is supposed to be coloured like its biggest node
  ## Step #1: find largest node per community
  #community_max <- c()
  #for (j in 1:length(communities)){
  #  #max_comm_size <- max(V(g)[communities[[j]]]$size)
  #  maximum_name <- V(g)[communities[[j]]][which.max(V(g)[communities[[j]]]$size)]$name
  #  community_max[j] <- maximum_name
  #}

  # Step #2: assign unique colour for largest quantile nodes
  graphs_largest <- V(g)[which(V(g)$size >= quantiles[quantile_step])]$name
  if (i > 1) {
    # get a named list where every new node is mapped to his predecessor
    graphs_largest_pre <- sapply(graphs_largest,
                                 function(x) find_largest_predecessor(graphs[[i-1]], g, x))
    # remove NA values, new nodes will be detected later anyway
    graphs_largest_pre <- graphs_largest_pre[!is.na(graphs_largest_pre)]

    predecessors_in_palette <- intersect(unname(graphs_largest_pre), names(graph_palette))
    if (length(predecessors_in_palette) > 0) {
      # get the new names for the palette by searching for their predecessors in the palette
      next_for_palette <- names(which(graphs_largest_pre == predecessors_in_palette))
      # rename them by matching their name to their predecessor, keep the same colour
      for (n in next_for_palette) {
        # get index of name to replace
        index <- which(names(graph_palette) == unname(graphs_largest_pre[n]))
        names(graph_palette)[index] <- n
      }
    }
  }
  missing <- setdiff(graphs_largest, names(graph_palette))
  for (m in missing) {
    #graph_palette[m] <- large_colour_palette[palette_index]
    graph_palette[m] <- col_vector[palette_index]
    #graph_palette[m] <- got_palette[palette_index]
    palette_index <- palette_index + 1
  }

  # Step #3: colour entire cluster of largest sections according to their 
  # unique colour IF they are the community largest
  #for (l in graphs_largest) {
  #  if (l %in% community_max) {
  #    comm_index <- membership(communities)[l]
  #    comm_nodes <- communities[[comm_index]]
  #    V(g)[comm_nodes]$col <- graph_palette[l]
  #  }
  #}
  # to avoid overwriting colour of largest node, let's manually assign it again
  for (l in graphs_largest) {
    V(g)[l]$col <- graph_palette[l]
  }

  # TODO: doing some double work here. If we already saw any of the
  # nodes, assign them their previous colour again
  for (l in V(g)$name) {
    if (l %in% names(graph_palette)){
      V(g)[l]$col <- graph_palette[l]
    } else {
      V(g)[l]$col <- "black"
    }
  }

  graph_name <- substr(g$version, 1, nchar(g$version)-4)
  g_layout <- create_layout(g, layout = "dh")
  lList[[i]] <- g_layout
  #pList[[i]] <- ggraph(g, layout = "stress") +
  pList[[i]] <- ggraph(g_layout) +
  geom_edge_link0(aes(edge_width = weight),edge_colour = "grey66")+
  #geom_node_point(aes(fill = clu,size = size),shape = 21)+
  geom_node_point(aes(fill = col, size = size),shape = 21)+
  geom_node_text(aes(filter = size >= unname(quantiles[quantile_step]), label = name),family="serif", size=4)+
  #scale_fill_manual(values = got_palette)+
  scale_edge_width(range = c(0.2,3))+
  scale_size(range = c(1,6))+
  theme_graph(base_family = "Helvetica")+
  theme(legend.position = "none") +
  ggtitle(graph_name)

  pList[[i]]
  
  graph_file_name <- file.path(d_dst, paste0(graph_name, ".pdf"))
  pdf(graph_file_name, width = 15, height = 10)
  plot(pList[[i]])
  dev.off()
}

#i <- 1
#while ((i+3)<=length(pList)) {
#  graph_file_name <- file.path(d_dst, paste0("graphs_", i, ".pdf"))
#  pdf(graph_file_name, width = 15, height = 10)
#  grid.arrange(pList[[i]], pList[[i+1]], pList[[i+2]], pList[[i+3]])
#  dev.off()
#  i <- i+4
#}
# TODO: die letzten 1-3 Plots noch mitnehmen

####################### ANIMATION TESTS
#
#nodes_lst <- lapply(1:length(graphs), function(i) {
#  cbind(igraph::as_data_frame(graphs[[i]], "vertices"),
#        x = lList[[i]][, 1], y = lList[[i]][, 2], frame = i
#  )
#})
#
#edges_lst <- lapply(1:length(graphs), function(i) cbind(igraph::as_data_frame(graphs[[i]], "edges"), frame = i))
#edges_lst <- lapply(1:length(graphs), function(i) {
#  edges_lst[[i]]$x <- nodes_lst[[i]]$x[match(edges_lst[[i]]$from, nodes_lst[[i]]$name)]
#  edges_lst[[i]]$y <- nodes_lst[[i]]$y[match(edges_lst[[i]]$from, nodes_lst[[i]]$name)]
#  edges_lst[[i]]$xend <- nodes_lst[[i]]$x[match(edges_lst[[i]]$to, nodes_lst[[i]]$name)]
#  edges_lst[[i]]$yend <- nodes_lst[[i]]$y[match(edges_lst[[i]]$to, nodes_lst[[i]]$name)]
#  edges_lst[[i]]$id <- paste0(edges_lst[[i]]$from, "-", edges_lst[[i]]$to)
#  edges_lst[[i]]$status <- TRUE
#  edges_lst[[i]]
#})
#
#all_edges <- do.call("rbind", lapply(graphs, get.edgelist))
#all_edges <- all_edges[!duplicated(all_edges), ]
#all_edges <- cbind(all_edges, paste0(all_edges[, 1], "-", all_edges[, 2]))
#
## TODO: idk, get this to work?
##edges_lst <- lapply(1:length(graphs), function(i) {
##  idx <- which(!all_edges[, 3] %in% edges_lst[[i]]$id)
##  if (length(idx != 0)) {
##    tmp <- data.frame(from = all_edges[idx, 1], to = all_edges[idx, 2], id = all_edges[idx, 3])
##    tmp$x <- nodes_lst[[i]]$x[match(tmp$from, nodes_lst[[i]]$name)]
##    tmp$y <- nodes_lst[[i]]$y[match(tmp$from, nodes_lst[[i]]$name)]
##    tmp$xend <- nodes_lst[[i]]$x[match(tmp$to, nodes_lst[[i]]$name)]
##    tmp$yend <- nodes_lst[[i]]$y[match(tmp$to, nodes_lst[[i]]$name)]
##    tmp$frame <- i
##    tmp$status <- FALSE
##    edges_lst[[i]] <- rbind(edges_lst[[i]], tmp)
##  }
##  edges_lst[[i]]
##})
#
#edges_df <- do.call("rbind", edges_lst)
#nodes_df <- do.call("rbind", nodes_lst)
#
#p <- ggplot() +
#  geom_segment(
#    data = edges_df,
#    aes(x = x, xend = xend, y = y, yend = yend, group = id, alpha = status),
#    show.legend = FALSE
#  ) +
#  geom_point(
#    data = nodes_df, aes(x, y, fill = col, group = name),
#    shape = 21, size = 4, show.legend = FALSE
#  ) +
#  scale_fill_manual(values = c("forestgreen", "grey25", "firebrick")) +
#  scale_alpha_manual(values = c(0, 1)) +
#  ease_aes("quadratic-in-out") +
#  transition_states(frame, state_length = 0.5, wrap = FALSE) +
#  labs(title = "Wave {closest_state}") +
#  theme_void()
#
#animate(plot = p, renderer = gifski_renderer())
#
#