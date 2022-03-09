#!/usr/bin/env Rscript

# TODO: KOMPLETT UEBERARBEITEN!
library(igraph)
library(ineq)
library(purrr)
library(logging)
library(ggplot2)
library(grid)

source("analyses/maintainers_graph_util.R")
source("fse22-artifact/util-networks-metrics.R")

projects <- c("linux", "xen", "u-boot", "qemu")
my.theme <- theme_bw(base_size = 12) + theme(legend.position = "top")

graph_name <- c()
project_column <- c()
#type <- c()
#value <- c()
section_number <- c()
cluster_number <- c()

#avg.cluster_quantity_list <- c()
#clusterquantity_quantile_list_05 <- c()
#clusterquantity_quantile_list_95 <- c()
#
#avg.degree_list <- c()
#degree_quantile_list_05 <- c()
#degree_quantile_list_95 <- c()
#
#cluster_avg.loc_list<- c()
#loc_quantile_list_05 <- c()
#loc_quantile_list_95 <- c()

#output_name <- file.path("resources", p, "/resources/graph_metrics.csv")
#cluster_output_name <- file.path("resources", p, "/resources/cluster_metrics.csv")
output_name <- "resources/number_metrics.csv"
#cluster_output_name <- "resources/cluster_metrics.csv"
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
    
    g_data <- maintainers_section_graph(p, file_name, file_map_name)
    g <- g_data$graph
    #cluster_g <- g_data$meta
    graph_name <- c(graph_name, file_name)
    project_column <- c(project_column, p)
    section_number <- c(section_number, length(V(g)))
    cluster_number <- c(cluster_number, length(g_data$bounds))

    # get sizes of communities
    #comm_sizes <- as.numeric(g_data$comm_groups %>% map(length))
    #value <- c(value, comm_sizes)
    #type[(length(type)+1):(length(type)+length(comm_sizes))] <- "community size"
    #graph_name[(length(graph_name)+1):(length(graph_name)+length(comm_sizes))] <- basename(file_name)
    #project_column[(length(project_column)+1):(length(project_column)+length(comm_sizes))] <- p
#
    #degrees <- unname(degree(g))
    #value <- c(value, degrees)
    #type[(length(type)+1):(length(type)+length(degrees))] <- "degree"
    #graph_name[(length(graph_name)+1):(length(graph_name)+length(degrees))] <- basename(file_name)
    #project_column[(length(project_column)+1):(length(project_column)+length(degrees))] <- p
    #
    #sizes_loc <- V(cluster_g)$size
    #value <- c(value, sizes_loc)
    #type[(length(type)+1):(length(type)+length(sizes_loc))] <- "cluster loc"
    #graph_name[(length(graph_name)+1):(length(graph_name)+length(sizes_loc))] <- basename(file_name)
    #project_column[(length(project_column)+1):(length(project_column)+length(sizes_loc))] <- p
    
    
    
    #quantiles <- quantile(comm_sizes, c(.95))
    #avg.cluster_quantity <- mean(comm_sizes)
    #avg.cluster_quantity_list <- c(avg.cluster_quantity_list, avg.cluster_quantity)
    #clusterquantity_quantile_list_95 <- c(clusterquantity_quantile_list_95, quantiles['95%'])
  #
    #quantiles <- quantile(unname(degree(g)), c(.95))
    #avg.degree = metrics.avg.degree(g)
    #avg.degree_list <- c(avg.degree_list, avg.degree)
    #degree_quantile_list_95 <- c(degree_quantile_list_95, quantiles['95%'])
  #
    ### cluster data
    #quantiles <- quantile(V(cluster_g)$size, c(.95))
    #cluster_avg.loc <- mean(V(cluster_g)$size)
    #cluster_avg.loc_list <- c(cluster_avg.loc_list, cluster_avg.loc)
    #loc_quantile_list_95 <- c(loc_quantile_list_95, quantiles['95%'])
  }
}

#df <- data.frame(graph_name, project_column, modularity_list, avg.path.length_list, density_list, 
#                 global.clustering.coefficient_list, local.avg.clustering.coefficient_list, 
#                 avg.degree_list, avg.cluster_quantity_list, hub.degree_list, scale.free.ness_list, gini.cluster_quantity_list, gini.degree_list)
#
#cluster_df <- data.frame(graph_name, project_column, cluster_modularity_list, cluster_avg.path.length_list, cluster_density_list,
#                 cluster_global.clustering.coefficient_list, cluster_local.avg.clustering.coefficient_list, cluster_avg.loc_list,
#                 cluster_avg.degree_list, cluster_hub.degree_list, cluster_scale.free.ness_list, cluster_gini.loc_list, cluster_gini.degree_list)

#df <- data.frame(graph_name, project_column, avg.degree_list,
#                 degree_quantile_list_95,
#                 avg.cluster_quantity_list, clusterquantity_quantile_list_95)
#
#cluster_df <- data.frame(graph_name, project_column, cluster_avg.loc_list, loc_quantile_list_95)
#df <- data.frame(graph_name, project_column, type, value)
df <- data.frame(graph_name, project_column, section_number, cluster_number)
write.csv(df, output_name)

quit()

# error plots !!!
df <- read.csv("resources/number_metrics.csv")
df <- ddply(df, .(project_column, graph_name, type), summarize, mean = mean(value), sd = round(sd(value), 2))

# todo: yadda yadda graph_name cutting, data merging by date yadda yadda
tmp_df <- df %>% filter(type == "community size")
ggplot(tmp_df, aes(x=date, y=mean, group=project_column, color=project_column)) + 
  geom_line() +
  geom_point()+
  geom_errorbar(aes(ymin=mean-sd, ymax=mean+sd), width=.2,
                position=position_dodge(0.05)) +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank()) +
  facet_wrap(~project_column, scales = "free")

ggplot(tmp_df, aes(x=graph_name, y=value, fill=project_column)) + 
  geom_boxplot()


#cluster_df <- data.frame(graph_name, project_column, cluster_avg.loc_list, loc_quantile_list_95)


#largest_t <- c(largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[3])]$name)
#second_largest_t <- c(second_largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[2])]$name)
#third_largest_t <- c(third_largest, V(g)[which(V(g)$size == tail(sort(V(g)$size),3)[1])]$name)
# TODO: merge this into paper-plots.R


f_releases <- 'resources/releases.csv'
load_releases <- function(filename) {
  data <- read_csv(filename)
  data <- data %>% mutate(date = as.Date(date))
}
if (!exists('releases')) {
  releases <- load_releases(f_releases)
}

df <- read.csv(output_name)
cluster_df <- read.csv(cluster_output_name)
df <- df[match(stringr::str_sort(df[["graph_name"]], numeric = TRUE), df[["graph_name"]]),]
cluster_df <- cluster_df[match(stringr::str_sort(cluster_df[["graph_name"]], numeric = TRUE), cluster_df[["graph_name"]]),]
df$graph_name = substr(df$graph_name, 1, nchar(df$graph_name)-4)
cluster_df$graph_name = substr(cluster_df$graph_name, 1, nchar(cluster_df$graph_name)-4)
df <- df %>% merge(releases, by.x = c("graph_name", "project_column"), by.y = c("release", "project"))
cluster_df <- cluster_df %>% merge(releases, by.x = c("graph_name", "project_column"), by.y = c("release", "project"))
#write.csv(df, output_name)
#write.csv(cluster_df, cluster_output_name)

# order data frames according to graph_name
#df$graph_name <- factor(df$graph_name, levels = df$graph_name)
#cluster_df$graph_name <- factor(cluster_df$graph_name, levels = cluster_df$graph_name)

# TODO: gleiche y-Achse
tmp_df <- df %>%
  select(avg.cluster_quantity_list, clusterquantity_quantile_list_95, date, project_column) %>%
  melt(id.vars = c('date', 'project_column'))
levels(tmp_df$variable)[levels(tmp_df$variable)=="avg.cluster_quantity_list"] <- "Average Cluster Quantity"
levels(tmp_df$variable)[levels(tmp_df$variable)=="clusterquantity_quantile_list_95"] <- "95% Quantile of Cluster Quantity"
pdf("sectiongraph_avgClusterQuantity.pdf", width = 15, height = 10)
#ggplot(df, aes(x=graph_name, avg.cluster_quantity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Average Cluster Quantity for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
ggplot(tmp_df, aes(x = date, y = value, color = variable, group=variable)) +
  geom_line() +
  stat_smooth() +
  ylab('Number of sections per Cluster') +
  xlab('Version') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank()) +
  facet_wrap(~project_column, scales = "free_x")
dev.off()

tmp_df <- df %>%
  select(avg.degree_list, degree_quantile_list_95, date, project_column) %>%
  melt(id.vars = c('date', 'project_column'))
levels(tmp_df$variable)[levels(tmp_df$variable)=="avg.degree_list"] <- "Average Degree"
levels(tmp_df$variable)[levels(tmp_df$variable)=="degree_quantile_list_95"] <- "95% Quantile of Degree"

pdf("sectiongraph_avgDegree.pdf", width = 15, height = 10)
ggplot(tmp_df, aes(x = date, y = value, color = variable, group=variable)) +
  geom_line() +
  stat_smooth() +
  ylab('Degree in Section Graph') +
  xlab('Version') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank()) +
  facet_wrap(~project_column, scales = "free_x")
#ggplot(df, aes(graph_name, avg.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Average Degree for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
dev.off()

tmp_df <- cluster_df %>%
  select(cluster_avg.loc_list, loc_quantile_list_95, date, project_column) %>%
  melt(id.vars = c('date', 'project_column'))
levels(tmp_df$variable)[levels(tmp_df$variable)=="cluster_avg.loc_list"] <- "Average LoC of a Cluster"
levels(tmp_df$variable)[levels(tmp_df$variable)=="loc_quantile_list_95"] <- "95% Quantile LoC in a Cluster"

pdf("clustergraph_avgLoC.pdf", width = 15, height = 10)
ggplot(tmp_df, aes(x = date, y = value, color = variable, group=variable)) +
  geom_line() +
  stat_smooth() +
  ylab('LoC in Cluster') +
  xlab('Version') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank()) +
  facet_wrap(~project_column, scales = "free_x")
#ggplot(cluster_df, aes(graph_name, cluster_avg.loc_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Cluster Average Lines of Code for Cluster Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
dev.off()

tmp_df <- cluster_df %>%
  select(cluster_avg.loc_list, date, project_column)
ggplot(tmp_df, aes(x = date, y = cluster_avg.loc_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('LoC in Cluster') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

tmp_df <- df %>%
  select(avg.cluster_quantity_list, date, project_column)
ggplot(tmp_df, aes(x = date, y = avg.cluster_quantity_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Cluster Quantity') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

tmp_df <- df %>%
  select(avg.degree_list, date, project_column)
ggplot(tmp_df, aes(x = date, y = avg.degree_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Average Degree') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

#levels(tmp_df$project_column)[levels(tmp_df$project_column)=="xen"] <- "Average LoC of a Cluster"
#levels(tmp_df$project_column)[levels(tmp_df$project_column)=="xen"] <- "Average LoC of a Cluster"
#levels(tmp_df$project_column)[levels(tmp_df$project_column)=="xen"] <- "Average LoC of a Cluster"
#levels(tmp_df$project_column)[levels(tmp_df$project_column)=="Linu"] <- "95% Quantile LoC in a Cluster"
### OLD COMPLEXITY STUFF

df <- read.csv("resources/old_graph_metrics.csv")
cluster_df <- read.csv("resources/old_cluster_metrics.csv")

df <- df %>% select(graph_name, project_column, modularity_list, density_list, hub.degree_list)
cluster_df <- cluster_df %>% select(graph_name, project_column, cluster_modularity_list, cluster_density_list, cluster_hub.degree_list)
df$graph_name = substr(df$graph_name, 1, nchar(df$graph_name)-4)
cluster_df$graph_name = substr(cluster_df$graph_name, 1, nchar(cluster_df$graph_name)-4)
df <- df %>% merge(releases, by.x = c("graph_name", "project_column"), by.y = c("release", "project"))
cluster_df <- cluster_df %>% merge(releases, by.x = c("graph_name", "project_column"), by.y = c("release", "project"))

# Modularity

ggplot(df, aes(x = date, y = modularity_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Modularity Section Graph') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

ggplot(cluster_df, aes(x = date, y = cluster_modularity_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Modularity Cluster Graph') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

# Hub Degree

ggplot(df, aes(x = date, y = hub.degree_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Hub Degree Section Graph') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

ggplot(cluster_df, aes(x = date, y = cluster_hub.degree_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Hub Degree Cluster Graph') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())
# Density

ggplot(df, aes(x = date, y = density_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Density Section Graph') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())

ggplot(cluster_df, aes(x = date, y = cluster_density_list, color = project_column, group=project_column)) +
  geom_line() +
  stat_smooth() +
  ylab('Density Cluster Graph') +
  xlab('Date') +
  my.theme +
    scale_x_date(date_breaks = '1 year', date_labels = '%Y',
                 #sec.axis = dup_axis(name = prj_releases,
                #                     breaks = releases$date,
                #                     labels = releases$release)
    ) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
        axis.title.x = element_blank(), legend.title = element_blank())
#pdf("density.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, density_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Density") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_density_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()


#pdf("sectiongraph_giniDegree.pdf", width = 15, height = 10)
##p1 <- ggplot(df, aes(graph_name, gini.degree_list)) + geom_point() +
##  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
##        axis.title.x = element_blank(), axis.title.y = element_blank()) +
##  ggtitle("Gini Degree") +
##  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
##p2 <- ggplot(cluster_df, aes(graph_name, cluster_gini.degree_list)) + geom_point() +
##  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
##        axis.title.x = element_blank(), axis.title.y = element_blank()) +
##  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
##grid.newpage()
#ggplot(df, aes(graph_name, gini.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Gini Degree for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("sectiongraph_giniClusterQuantity.pdf", width = 15, height = 10)
#ggplot(df, aes(graph_name, gini.cluster_quantity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Gini Cluster Quantity for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("sectiongraph_avgClusterQuantity.pdf", width = 15, height = 10)
#ggplot(df, aes(graph_name, avg.cluster_quantity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Average Cluster Quantity for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("sectiongraph_avgDegree.pdf", width = 15, height = 10)
#ggplot(df, aes(graph_name, avg.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Average Degree for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("clustergraph_avgLoC.pdf", width = 15, height = 10)
#ggplot(cluster_df, aes(graph_name, cluster_avg.loc_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Cluster Average Lines of Code for Cluster Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("clustergraph_giniDegree.pdf", width = 15, height = 10)
#ggplot(cluster_df, aes(graph_name, cluster_gini.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Gini Degree for Cluster Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("clustergraph_giniLoC.pdf", width = 15, height = 10)
#ggplot(cluster_df, aes(graph_name, cluster_gini.loc_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Cluster Gini Lines of Code for Cluster Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#dev.off()
#
#pdf("clustergraph_avgDegree.pdf", width = 15, height = 10)
#ggplot(cluster_df, aes(graph_name, cluster_avg.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free") +
#  ggtitle("Average Degree for Cluster Graph")
#dev.off()
#
#ggplot(df, aes(graph_name, avg.cluster_quantity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Average Cluster Quantity for Section Graph") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")

#pdf("avgPathLength.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, avg.path.length_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Modularity") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_modularity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()

#pdf("density.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, density_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Density") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_density_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()

#pdf("globalClusteringCoefficient.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, global.clustering.coefficient_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Global Clustering Coefficient") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_global.clustering.coefficient_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()
#
#pdf("localAvgClusteringCoefficient.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, local.avg.clustering.coefficient_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Local Clustering Coefficient") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_local.avg.clustering.coefficient_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()

#pdf("modularity.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, modularity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Modularity") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_modularity_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()

#pdf("hubDegree.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, hub.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Hub Degree") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_hub.degree_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()
#
#pdf("scalefreeness.pdf", width = 15, height = 10)
#p1 <- ggplot(df, aes(graph_name, scale.free.ness_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  ggtitle("Scale Freeness") +
#  geom_line(group=1) + stat_smooth() + facet_wrap(~project_column, scales = "free")
#p2 <- ggplot(cluster_df, aes(graph_name, cluster_scale.free.ness_list)) + geom_point() +
#  theme(axis.text.x = element_text(angle = 45, hjust = 1.25),
#        axis.title.x = element_blank(), axis.title.y = element_blank()) +
#  geom_line(group=1) + facet_wrap(~project_column, scales = "free")
#
#grid.newpage()
#grid.draw(rbind(ggplotGrob(p1), ggplotGrob(p2), size = "last"))
#dev.off()

##df <- df[match(stringr::str_sort(df[["graph_name"]], numeric = TRUE), df[["graph_name"]]),]
#cluster_dir_name <- "resources/linux/resources/maintainers_cluster"
#cluster_files <- list.files(path = cluster_dir_name, pattern = "*.csv", full.names = TRUE, recursive = FALSE)
#cluster_files <- cluster_files[!grepl("-rc", cluster_files, fixed = TRUE)]
#cluster_files <- stringr::str_sort(cluster_files, numeric = TRUE)
#
#rep_list <- list()
#
#previous_df <- read.csv(cluster_files[1])
#rep_list[[basename(cluster_files[1])]] <- unique(previous_df$c_representative)
#
#for (i in 2:length(cluster_files)) {
#  file_name <- cluster_files[i]
#  previous_file_name <- cluster_files[i-1]
#  df <- read.csv(file_name)
#  # get current cluster representatives
#  cluster_reps <- unique(df$c_representative)
#  # get the previous cluster representatives from the previous version from
#  # the already stored rep_list by accessing them through the previous file_name
#  predecessors <- rep_list[[basename(previous_file_name)]]
#
#  new_reps <- c()
#  # for all predecessors, find the one next cluster_rep, that overlaps the most
#  for (c_p_index in 1:length(predecessors)) {
#    c_p <- predecessors[c_p_index]
#    #print("BEFORE")
#    #print(c_p_index)
#    # if a cluster_rep was deleted (which can happen if all next clusters had
#    # 0 overlap), we simply skip this entry. It will stay empty now
#    if (is.null(c_p)) {
#      next
#    }
#    max_c <- NA
#    max_overlap <- 0
#    # we iterate over all new cluster_reps to get the one with the highest
#    # overlap
#    for (c in cluster_reps) {
#      #print("MIDDLE")
#      #print(c)
#      overlap <- compare_cluster_csv(previous_df, df, c_p, c)
#      if (overlap > max_overlap) {
#        max_c <- c
#        max_overlap <- overlap
#      }
#    }
#    # we store the one with the highest overlap where the original predecessor
#    # was
#    # TODO Delme
#    #print("AFTER")
#    print(c_p_index)
#    new_reps[c_p_index] <- max_c
#
#    # with this approach, there could still be new clusters missing now, since
#    # we iterated over the predecessors. We need to now detect and keep track
#    # of all new clusters by letting them trail the new representatives
#    missed_reps <- setdiff(cluster_reps, new_reps)
#    new_reps <- c(new_reps, missed_reps)
#  }
#  rep_list[[basename(file_name)]] <- new_reps
#  previous_df <- df
#}
#
#max_cluster_length <- max(unlist(lapply(rep_list, length)))
## add padding NA's at the end of each vector
#rep_list <- lapply(rep_list, function(x) x <- c(x, rep(NA, max_cluster_length-length(x))))
#final_df <- as.data.frame(rep_list, col.names = basename(cluster_files))
#write.table(final_df, "rep_list.csv", row.names = FALSE, sep = ",")
