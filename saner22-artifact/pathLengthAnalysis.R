
library(igraph)
library(ineq)
library(purrr)
library(logging)
library(ggplot2)
library(grid)

source("analyses/maintainers_graph_util.R")
source("saner22-artifact/util-networks-metrics.R")

projects <- c("linux", "xen", "u-boot", "qemu")
my.theme <- theme_bw(base_size = 12) + theme(legend.position = "top")

graph_name <- c()
project_column <- c()
avg.path.length_list <- c()
cluster_index_list <- c()

for (p in projects) {
  #data_dir_name <- "resources/linux/resources/maintainers_section_graph"
  #output_name <- "resources/linux/resources/graph_metrics_new.csv"
  #cluster_output_name <- "resources/linux/resources/cluster_graph_metrics_new.csv"
  data_dir_name <- file.path("resources", p, "resources/maintainers_section_graph")
  
  files <- list.files(path = data_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
  files <- files[!grepl("-rc", files, fixed = TRUE)]
  files <- files[!grepl("filemap", files, fixed = TRUE)]
  
  for (file_name in files) {
    print(file_name)
    
    #TODO: hier erste Variable als echten Graphnamen abspeichern lassen
    file_map_name <- substr(basename(file_name), 1, nchar(basename(file_name))-4)
    file_map_name <- paste0(file_map_name, "_filemap.csv")
    file_map_name <- sub(basename(file_name), file_map_name, file_name)
    
    g_data <- maintainers_section_graph(file_name, p, file_map_name)
    g <- g_data$graph
    bounds <- g_data$bounds
    comm_groups <- g_data$comm_groups
    
    for (i in bounds) {
      group <- comm_groups[i]
      group_list <- unname(group)[[1]]
      cluster_graph <- igraph::delete_vertices(g, which(!(V(g)$name %in% group_list)))

      graph_name <- c(graph_name, basename(file_name))
      cluster_index_list <- c(cluster_index_list, i)
      project_column <- c(project_column, p)
      avg.path.length_list <- c(avg.path.length_list, metrics.avg.pathlength(cluster_graph, directed = FALSE))
    }
  }
}


f_releases <- 'resources/releases.csv'
load_releases <- function(filename) {
  data <- read_csv(filename)
  data <- data %>% mutate(date = as.Date(date))
}
if (!exists('releases')) {
  releases <- load_releases(f_releases)
}

df <- data.frame(graph_name, project_column, cluster_index_list, avg.path.length_list)
write.csv(df, "resources/avg_path_length.csv")
# substitue NaN with 0
#df$avg.path.length_list[is.nan(df$avg.path.length_list)] <- 0
#df$graph_name = substr(df$graph_name, 1, nchar(df$graph_name)-4)
#df <- df %>% merge(releases, by.x = c("graph_name", "project_column"), by.y = c("release", "project"))
#
##df <- df %>% filter(project_column == "linux")
#ggplot(df, aes(x=date, y=avg.path.length_list)) + 
#  geom_boxplot() +
#  my.theme +
#    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
#                 #sec.axis = dup_axis(name = prj_releases,
#                #                     breaks = releases$date,
#                #                     labels = releases$release)
#    ) +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), legend.title = element_blank()) +
#  facet_wrap(~project_column, scales = "free")
