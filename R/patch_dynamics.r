library(reshape2)
library(ggplot2)

rm(list = ls())

#commit_description <- read.csv("/home/ralf/workspace/PreemptRTAnalyse/commit-description", header=TRUE, sep=' ')

patch_flow <- read.csv("/home/ralf/workspace/PaStA/R/preemptrt-patch-flow", header=TRUE, sep=' ')
#patch_flow <- read.csv("/home/ralf/workspace/PaStA/R/preemptrt-patch-flow-condensed", header=TRUE, sep=' ')
#patch_flow <- read.csv("/home/ralf/workspace/PaStA/R/preemptrt-patch-flow-condensed_2", header=TRUE, sep=' ')

patch_flow$versions <- factor(patch_flow$versions, levels = patch_flow$versions)

#patch_flow <- head(patch_flow, 100)

patch_flow.molten <- melt(patch_flow,
                          id.vars = c("versions",
                                      "left_release_date",
                                      "right_release_date",
                                      "num_patches_left",
                                      "num_patches_right"))

p = ggplot(patch_flow.molten, aes(x=versions, y=value, fill=variable)) +
	theme(axis.text.x = element_text(angle = 55, hjust = 1, size=25),
	      axis.title.x = element_blank(),
	      axis.title.y = element_blank(),
	      axis.text.y = element_text(hjust = 1, size=25),
	      legend.text = element_text(size=25),
	      legend.position="top", legend.direction="horizontal") + 
	geom_bar(stat = "identity") +
  guides(fill=guide_legend(title=NULL))
q = ggplot(patch_flow, aes(x=versions, y=upstream)) + geom_bar(stat = "identity")

print(p)
#print(q)
