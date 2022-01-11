#!/usr/bin/env Rscript

library(igraph)
library(ineq)
library(purrr)
library(logging)
library(ggplot2)
library(grid)

source("analyses/mtr_sctn_graph_util.R")
source("saner22-artifact/util-networks-metrics.R")

data_dir_name <- "resources/linux/resources/maintainers_section_graph"
output_name <- "resources/linux/resources/graph_metrics_new.csv"
cluster_output_name <- "resources/linux/resources/cluster_graph_metrics_new.csv"

files <- list.files(path = data_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
files <- files[!grepl("-rc", files, fixed = TRUE)]
files <- files[!grepl("filemap", files, fixed = TRUE)]
graph_name <- c()

cluster.number_list <- c()
gini.degree_list <- c()
gini.cluster_quantity_list <- c()
avg.cluster_quantity_list <- c()
modularity_list <- c()
avg.path.length_list <- c()
density_list <- c()
global.clustering.coefficient_list <- c()
local.avg.clustering.coefficient_list <- c()
avg.degree_list <- c()
hub.degree_list <- c()
small.world.ness_list <- c()
scale.free.ness_list <- c()

cluster_gini.degree_list <- c()
cluster_gini.loc_list<- c()
cluster_avg.loc_list<- c()
cluster_modularity_list <- c()
cluster_avg.path.length_list <- c()
cluster_density_list <- c()
cluster_global.clustering.coefficient_list <- c()
cluster_local.avg.clustering.coefficient_list <- c()
cluster_avg.degree_list <- c()
cluster_hub.degree_list <- c()
cluster_small.world.ness_list <- c()
cluster_scale.free.ness_list <- c()

largest <- c()
second_largest <- c()
third_largest <- c()

for (file_name in files) {
#  g <- get(load(file_name))
#  # get walktrap clustering
#  wt_comm <- cluster_walktrap(g)
#
#  # get number of existing clusters within graph as bounds for processing
#  comm_groups <- igraph::groups(wt_comm)
#  bounds <- seq(1, length(comm_groups), 1)
#
  # Gini coefficient for degree of sections
  
  file_map_name <- substr(basename(file_name), 1, nchar(basename(file_name))-4)
  file_map_name <- paste0(file_map_name, "_filemap.csv")
  file_map_name <- sub(basename(file_name), file_map_name, file_name)
  
  g_data <- maintainers_section_graph(file_name, "linux", file_map_name)
  g <- g_data$graph
  cluster_g <- g_data$meta

  graph_name <- c(graph_name, basename(file_name))

  gini.degree <- Gini(unname(degree(g)))
  gini.degree_list <- c(gini.degree_list, gini.degree)

  comm_sizes <- as.numeric(g_data$comm_groups %>% map(length))
  avg.cluster_quantity <- mean(comm_sizes)
  avg.cluster_quantity_list <- c(avg.cluster_quantity_list, avg.cluster_quantity)

  gini.cluster_quantity <- Gini(unname(comm_sizes))
  gini.cluster_quantity_list <- c(gini.cluster_quantity_list, gini.cluster_quantity)
  
  modularity <- metrics.modularity(g)
  modularity_list <- c(modularity_list, modularity)

  avg.path.length <- metrics.avg.pathlength(g)
  avg.path.length_list <- c(avg.path.length_list, avg.path.length)

  density <- metrics.density(g)
  density_list <- c(density_list, density)

  global.clustering.coefficient <- metrics.clustering.coeff(g, cc.type="global")
  global.clustering.coefficient_list <- c(global.clustering.coefficient_list, global.clustering.coefficient)

  local.avg.clustering.coefficient <- metrics.clustering.coeff(g, cc.type="localaverage")
  local.avg.clustering.coefficient_list <- c(local.avg.clustering.coefficient_list, local.avg.clustering.coefficient)

  avg.degree = metrics.avg.degree(g)
  avg.degree_list <- c(avg.degree_list, avg.degree)

  hub.degree = metrics.hub.degree(g)[["degree"]]
  hub.degree_list <- c(hub.degree_list, hub.degree)
  
  scale.free.ness = metrics.is.scale.free(g)
  scale.free.ness_list <- c(scale.free.ness_list, scale.free.ness)
  
  ## cluster data
  cluster_gini.degree <- Gini(unname(degree(cluster_g)))
  cluster_gini.degree_list <- c(cluster_gini.degree_list, cluster_gini.degree)

  cluster_avg.loc <- mean(V(cluster_g)$size)
  cluster_avg.loc_list <- c(cluster_avg.loc_list, cluster_avg.loc)

  cluster_gini.loc <- Gini(V(cluster_g)$size)
  cluster_gini.loc_list <- c(cluster_gini.loc_list, cluster_gini.loc)

  cluster_modularity <- metrics.modularity(cluster_g)
  cluster_modularity_list <- c(cluster_modularity_list, cluster_modularity)
  
  cluster_avg.path.length <- metrics.avg.pathlength(cluster_g)
  cluster_avg.path.length_list <- c(cluster_avg.path.length_list, cluster_avg.path.length)

  cluster_density <- metrics.density(cluster_g)
  cluster_density_list <- c(cluster_density_list, cluster_density)

  cluster_global.clustering.coefficient <- metrics.clustering.coeff(cluster_g, cc.type="global")
  cluster_global.clustering.coefficient_list <- c(cluster_global.clustering.coefficient_list, cluster_global.clustering.coefficient)

  cluster_local.avg.clustering.coefficient <- metrics.clustering.coeff(cluster_g, cc.type="localaverage")
  cluster_local.avg.clustering.coefficient_list <- c(cluster_local.avg.clustering.coefficient_list, cluster_local.avg.clustering.coefficient)

  cluster_avg.degree = metrics.avg.degree(cluster_g)
  cluster_avg.degree_list <- c(cluster_avg.degree_list, cluster_avg.degree)

  cluster_hub.degree = metrics.hub.degree(cluster_g)[["degree"]]
  cluster_hub.degree_list <- c(cluster_hub.degree_list, cluster_hub.degree)

  cluster_scale.free.ness = metrics.is.scale.free(cluster_g)
  cluster_scale.free.ness_list <- c(cluster_scale.free.ness_list, cluster_scale.free.ness)

  #small.world.ness = metrics.is.smallworld(g)
  #small.world.ness_list <- c(small.world.ness_list, small.world.ness)

  
  #largest <- c(largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[3])]$name)
  #second_largest <- c(second_largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[2])]$name)
  #third_largest <- c(third_largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[1])]$name)

}

df <- data.frame(graph_name, modularity_list, avg.path.length_list, density_list, 
                 global.clustering.coefficient_list, local.avg.clustering.coefficient_list, 
                 avg.degree_list, hub.degree_list, scale.free.ness_list)

cluster_df <- data.frame(graph_name, cluster_modularity_list, cluster_avg.path.length_list, cluster_density_list,
                 cluster_global.clustering.coefficient_list, cluster_local.avg.clustering.coefficient_list,
                 cluster_avg.degree_list, cluster_hub.degree_list, cluster_scale.free.ness_list)


largest_t <- c(largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[3])]$name)
second_largest_t <- c(second_largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[2])]$name)
third_largest_t <- c(third_largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[1])]$name)

df <- df[match(stringr::str_sort(df[["graph_name"]], numeric = TRUE), df[["graph_name"]]),]
cluster_df <- df[match(stringr::str_sort(cluster_df[["graph_name"]], numeric = TRUE), cluster_df[["graph_name"]]),]
write.csv(df, output_name)
write.csv(cluster_df, cluster_output_name)

# order data frames according to graph_name
df$graph_name <- factor(df$graph_name, levels = df$graph_name)
cluster_df$graph_name <- factor(cluster_df$graph_name, levels = cluster_df$graph_name)

pdf("giniDegree.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, gini.degree_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Gini Degree") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_gini.degree_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)
grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("giniClusterQuantity.pdf", width = 15, height = 10)
ggplot(df, aes(graph_name, gini.cluster_quantity_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Gini Cluster Quantity -- Important: ONLY section graph here") +
  geom_line(group=1) + stat_smooth()
dev.off()

pdf("avgClusterQuantity.pdf", width = 15, height = 10)
ggplot(df, aes(graph_name, avg.cluster_quantity_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Average Cluster Quantity -- Important: ONLY section graph here") +
  geom_line(group=1) + stat_smooth()
dev.off()

pdf("avgLoC.pdf", width = 15, height = 10)
ggplot(df, aes(graph_name, cluster_avg.loc_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Cluster Average Lines of Code -- Important: ONLY cluster graph here") +
  geom_line(group=1) + stat_smooth()
dev.off()

pdf("giniLoC.pdf", width = 15, height = 10)
ggplot(df, aes(graph_name, cluster_gini.loc_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Cluster Gini Lines of Code -- Important: ONLY cluster graph here") +
  geom_line(group=1) + stat_smooth()
dev.off()


pdf("modularity.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, modularity_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Modularity") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_modularity_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)
grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))

dev.off()

pdf("avgPathLength.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, avg.path.length_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Modularity") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_modularity_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("density.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, density_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Density") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_density_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("globalClusteringCoefficient.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, global.clustering.coefficient_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Global Clustering Coefficient") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_global.clustering.coefficient_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("localAvgClusteringCoefficient.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, local.avg.clustering.coefficient_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Local Clustering Coefficient") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_local.avg.clustering.coefficient_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("avgDegree.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, avg.degree_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Average Degree") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_avg.degree_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("hubDegree.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, hub.degree_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Hub Degree") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_hub.degree_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

pdf("scalefreeness.pdf", width = 15, height = 10)
p1 <- ggplot(df, aes(graph_name, scale.free.ness_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  ggtitle("Scale Freeness") +
  geom_line(group=1) + stat_smooth()
p2 <- ggplot(cluster_df, aes(graph_name, cluster_scale.free.ness_list)) + geom_point() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), axis.title.y = element_blank()) +
  geom_line(group=1)

grid.newpage()
grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
dev.off()

#df <- df[match(stringr::str_sort(df[["graph_name"]], numeric = TRUE), df[["graph_name"]]),]
cluster_dir_name <- "resources/linux/resources/maintainers_cluster"
cluster_files <- list.files(path = cluster_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
cluster_files <- cluster_files[!grepl("-rc", cluster_files, fixed = TRUE)]
cluster_files <- stringr::str_sort(cluster_files, numeric = TRUE)

rep_list <- list()

previous_df <- read.csv(cluster_files[1])
rep_list[[basename(cluster_files[1])]] <- unique(previous_df$c_representative)

for (i in 2:length(cluster_files)) {
  file_name <- cluster_files[i]
  previous_file_name <- cluster_files[i-1]
  df <- read.csv(file_name)
  # get current cluster representatives
  cluster_reps <- unique(df$c_representative)
  # get the previous cluster representatives from the previous version from
  # the already stored rep_list by accessing them through the previous file_name
  predecessors <- rep_list[[basename(previous_file_name)]]

  new_reps <- c()
  # for all predecessors, find the one next cluster_rep, that overlaps the most
  for (c_p_index in 1:length(predecessors)) {
    c_p <- predecessors[c_p_index]
    #print("BEFORE")
    #print(c_p_index)
    # if a cluster_rep was deleted (which can happen if all next clusters had
    # 0 overlap), we simply skip this entry. It will stay empty now
    if (is.null(c_p)) {
      next
    }
    max_c <- NA
    max_overlap <- 0
    # we iterate over all new cluster_reps to get the one with the highest
    # overlap
    for (c in cluster_reps) {
      #print("MIDDLE")
      #print(c)
      overlap <- compare_cluster_csv(previous_df, df, c_p, c)
      if (overlap > max_overlap) {
        max_c <- c
        max_overlap <- overlap
      }
    }
    # we store the one with the highest overlap where the original predecessor
    # was
    # TODO Delme
    #print("AFTER")
    print(c_p_index)
    new_reps[c_p_index] <- max_c

    # with this approach, there could still be new clusters missing now, since
    # we iterated over the predecessors. We need to now detect and keep track
    # of all new clusters by letting them trail the new representatives
    missed_reps <- setdiff(cluster_reps, new_reps)
    new_reps <- c(new_reps, missed_reps)
  }
  rep_list[[basename(file_name)]] <- new_reps
  previous_df <- df
}

max_cluster_length <- max(unlist(lapply(rep_list, length)))
# add padding NA's at the end of each vector
rep_list <- lapply(rep_list, function(x) x <- c(x, rep(NA, max_cluster_length-length(x))))
final_df <- as.data.frame(rep_list, col.names = basename(cluster_files))
write.table(final_df, "rep_list.csv", row.names = FALSE, sep = ",")
