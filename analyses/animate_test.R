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
library(graphlayouts)
library(RColorBrewer)
library(tikzDevice)
library(parallel)

source("analyses/maintainers_graph_util.R")

args <- commandArgs(trailingOnly = TRUE)
filter_version <- NULL
if (length(args) == 0) {
  data_dir_name <- file.path("resources", project, "resources/maintainers_section_graph")
  d_dst <- file.path("resources", project, "resources/maintainers_daumenkino")
} else {
  data_dir_name <- args[1]
  d_dst <- args[2]
  ver_arg <- grep("^--version=", args, value = TRUE)
  if (length(ver_arg) > 0)
    filter_version <- sub("^--version=", "", ver_arg)
}
dir.create(d_dst, showWarnings = FALSE, recursive = TRUE)

QUANTILE_STEP <- 0.90
WIDTH <- 9
HEIGHT <- 6

files <- list.files(path = data_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
files <- files[!grepl("-rc", files, fixed = TRUE)]
files <- files[!grepl("filemap", files, fixed = TRUE)]
files <- stringr::str_sort(files, numeric = TRUE)
if (project == "qemu") {
  files <- files[18:79]
}

cluster_cache <- list()

load_cluster_csv <- function(version) {
  if (is.null(cluster_cache[[version]])) {
    path <- file.path("resources", project, "resources/maintainers_cluster", version)
    cluster_cache[[version]] <<- read.csv(path)
  }
  cluster_cache[[version]]
}

# g_v1 is the previous graph, g_v2 is the follower, node_name is ONE node of g_v2
find_largest_predecessor <- function(g_v1, g_v2, node_name) {
  version1 <- g_v1$version
  version2 <- g_v2$version

  df_1 <- load_cluster_csv(version1)
  df_2 <- load_cluster_csv(version2)

  max <- which.max(sapply(V(g_v1)$name,
                          function(x) compare_cluster_csv(df_1, df_2, x, node_name)))
  df_2 <- df_2[df_2$c_representative == node_name,]
  max_name <- names(max)
  condition_cluster_diverted <- (max_name != node_name) && !(max_name %in% df_2$c_section)
  if ((unname(max) == 0) || condition_cluster_diverted) {
    max <- NA
  } else {
    max <- max_name
  }
  return(max)
}

# ===== FIRST PASS =====
# Load all graphs, remove isolated nodes, track large-node identity across
# versions and assign colours.  We call find_largest_predecessor once per
# large node per version and reuse the result for both tasks.

qual_col_pals <- brewer.pal.info[brewer.pal.info$category == 'qual',]
col_vector    <- unlist(mapply(brewer.pal, qual_col_pals$maxcolors, rownames(qual_col_pals)))
palette_index <- 1
graph_palette <- list()

n_files <- length(files)
cat(sprintf("Loading %d versions in parallel...\n", n_files))
graphs_raw <- mclapply(seq_along(files), function(k) {
  file_name     <- files[k]
  file_map_name <- sub("\\.csv$", "_filemap.csv", file_name)
  g_data <- maintainers_section_graph(project, file_name, file_map_name)
  g <- g_data$meta
  g$version <- basename(file_name)
  delete_vertices(g, which(degree(g) == 0))
}, mc.cores = detectCores())
cat("Loading done.\n")

graphs         <- list()
large_by_ver   <- list()  # large_by_ver[[i]]:  current names of large nodes in version i
large_canonical <- list() # large_canonical[[i]]: named vector current_name -> canonical_name
ever_large     <- character(0)

for (k in seq_along(files)) {
  g <- graphs_raw[[k]]
  i <- k
  graphs[[i]] <- g

  qs    <- quantile(V(g)$size, QUANTILE_STEP)
  large <- V(g)[V(g)$size >= qs]$name
  large_by_ver[[i]] <- large

  # Compute predecessor map once for all large nodes in this version
  if (i > 1) {
    prev_g <- graphs[[i - 1]]
    preds  <- sapply(large, function(x) find_largest_predecessor(prev_g, g, x))
  } else {
    preds <- setNames(rep(NA_character_, length(large)), large)
  }

  # --- canonical name tracking ---
  prev_canon <- if (i > 1) large_canonical[[i - 1]] else list()
  canon <- setNames(large, large)
  for (node in large) {
    pred <- preds[[node]]
    if (!is.na(pred) && pred %in% names(prev_canon)) {
      canon[node] <- prev_canon[[pred]]
    }
  }
  large_canonical[[i]] <- canon
  ever_large <- union(ever_large, unname(canon))

  # --- colour tracking ---
  V(g)$col <- "black"

  preds_valid <- preds[!is.na(preds)]
  predecessors_in_palette <- intersect(unname(preds_valid), names(graph_palette))
  if (length(predecessors_in_palette) > 0) {
    next_for_palette <- names(which(preds_valid %in% predecessors_in_palette))
    for (n in next_for_palette) {
      index <- which(names(graph_palette) == unname(preds_valid[n]))
      names(graph_palette)[index] <- n
    }
  }
  for (m in setdiff(large, names(graph_palette))) {
    graph_palette[[m]] <- unname(col_vector[palette_index])
    palette_index <- palette_index + 1
  }
  for (l in V(g)$name) {
    if (l %in% names(graph_palette))
      V(g)[l]$col <- graph_palette[[l]]
  }

  graphs[[i]] <- g
}

# ===== REFERENCE LAYOUT =====
# Build a single union graph over ALL nodes ever seen (identified by their
# section-representative name), with edges aggregated across every version.
# We lay this out ONCE with a stress layout, and every node is drawn at its
# fixed reference position in every version.  This keeps the whole picture
# coordinated (edge lengths consistent) and perfectly stable across the
# sequence, while the stress layout of the full graph reveals the natural
# spatial clustering.

all_names <- unique(unlist(lapply(graphs, function(g) V(g)$name)))
cat(sprintf("Computing reference layout for %d nodes...\n", length(all_names)))

edge_weights <- list()  # keyed by "nameA|nameB" (sorted) -> summed weight
for (g in graphs) {
  if (ecount(g) == 0)
    next
  el <- igraph::as_data_frame(g, what = "edges")
  for (r in seq_len(nrow(el))) {
    a <- el$from[r]; b <- el$to[r]
    if (a == b)
      next
    key <- paste(sort(c(a, b)), collapse = "|")
    w   <- if (is.null(el$weight)) 1 else el$weight[r]
    edge_weights[[key]] <- (if (is.null(edge_weights[[key]])) 0 else edge_weights[[key]]) + w
  }
}

union_g <- make_empty_graph(directed = FALSE)
union_g <- add_vertices(union_g, length(all_names), name = all_names)
if (length(edge_weights) > 0) {
  parts <- strsplit(names(edge_weights), "|", fixed = TRUE)
  ends  <- unlist(lapply(parts, function(p) match(p, all_names)))
  union_g <- add_edges(union_g, ends, weight = unlist(edge_weights))
}

# Force-directed (Fruchterman-Reingold) with log-scaled LoC edge weights:
# strongly connected sections pull together, pendant sections hug their hub,
# and the whole picture is dense and organic.  Seeded for reproducibility.
set.seed(1)
ref_layout <- igraph::layout_with_fr(union_g, weights = log1p(E(union_g)$weight))

# The graph is ~60% degree-1 pendants, so FR's repulsion flings the periphery
# far out.  Compress radially about the centroid (r' = R * (r/R)^GAMMA, GAMMA<1)
# to pull the outskirts in and make the whole picture dense.
GAMMA <- 0.40
cx <- mean(ref_layout[, 1]); cy <- mean(ref_layout[, 2])
dx <- ref_layout[, 1] - cx;  dy <- ref_layout[, 2] - cy
r  <- sqrt(dx^2 + dy^2); R <- max(r)
rn <- ifelse(r == 0, 0, R * (r / R)^GAMMA)
th <- atan2(dy, dx)
ref_layout <- cbind(cx + rn * cos(th), cy + rn * sin(th))

# Pull degree-1 pendants in toward their hub so they form a tight halo instead
# of long radial spokes: p' = hub + PENDANT_PULL * (p - hub).
PENDANT_PULL <- 0.20
udeg <- degree(union_g)
for (v in which(udeg == 1)) {
  h <- as.integer(neighbors(union_g, v))[1]
  ref_layout[v, ] <- ref_layout[h, ] + PENDANT_PULL * (ref_layout[v, ] - ref_layout[h, ])
}

rownames(ref_layout) <- all_names
cat("Reference layout done.\n")

# ===== SECOND PASS: render =====

render_version <- function(i) {
  g          <- graphs[[i]]
  pos        <- ref_layout[V(g)$name, , drop = FALSE]

  g_layout   <- create_layout(g, layout = "manual", x = pos[, 1], y = pos[, 2])
  quantiles  <- quantile(V(g)$size, QUANTILE_STEP)
  graph_name <- sub("\\.csv$", "", g$version)
  cat(sprintf("[%d/%d] Rendering %s\n", i, length(graphs), graph_name))

  p <- ggraph(g_layout) +
    geom_edge_link0(aes(edge_width = weight), edge_colour = "grey66") +
    geom_node_point(aes(fill = col, size = size), shape = 21) +
    geom_node_text(aes(filter = size >= quantiles, label = name),
                   family = "serif", size = 4, repel = TRUE) +
    scale_fill_identity() +
    scale_edge_width(range = c(0.2, 3)) +
    scale_size(range = c(1, 6)) +
    theme_graph(base_family = "Helvetica") +
    theme(legend.position = "none") +
    ggtitle(graph_name)

  pdf(file.path(d_dst, paste0(graph_name, ".pdf")), width = WIDTH, height = HEIGHT)
  plot(p)
  dev.off()

  tikz(file.path(d_dst, paste0(graph_name, ".tex")),
       width = WIDTH, height = HEIGHT, sanitize = TRUE, standAlone = TRUE)
  plot(p)
  dev.off()
}

render_indices <- seq_along(graphs)
if (!is.null(filter_version)) {
  render_indices <- which(sapply(graphs, function(g)
    sub("\\.csv$", "", g$version) == filter_version))
  cat(sprintf("Rendering version %s only.\n", filter_version))
} else {
  cat(sprintf("Rendering %d versions...\n", length(graphs)))
}
for (i in render_indices) render_version(i)
cat("Done.\n")
