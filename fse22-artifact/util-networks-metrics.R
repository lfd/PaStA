## This file is part of coronet, which is free software: you
## can redistribute it and/or modify it under the terms of the GNU General
## Public License as published by  the Free Software Foundation, version 2.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License along
## with this program; if not, write to the Free Software Foundation, Inc.,
## 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
##
## Copyright 2015, 2019 by Thomas Bock <bockthom@fim.uni-passau.de>
## Copyright 2021 by Thomas Bock <bockthom@cs.uni-saarland.de>
## Copyright 2017 by Raphael Nömmer <noemmer@fim.uni-passau.de>
## Copyright 2017-2019 by Claus Hunsen <hunsen@fim.uni-passau.de>
## Copyright 2017-2018 by Christian Hechtl <hechtl@fim.uni-passau.de>
## Copyright 2018 by Barbara Eckl <ecklbarb@fim.uni-passau.de>
## Copyright 2021 by Niklas Schneider <s8nlschn@stud.uni-saarland.de>
## All Rights Reserved.


## / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / /
## Libraries ---------------------------------------------------------------

requireNamespace("igraph")


## / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / / /
## Metric functions --------------------------------------------------------

#' Determine the maximum degree for the given network.
#'
#' @param network the network to be examined
#' @param mode the mode to be used for determining the degrees [default: "total"]
#'
#' @return A data frame containing the name of the vertex with with maximum degree its degree.
metrics.hub.degree = function(network, mode = c("total", "in", "out")) {
    ## check whether the network is empty, i.e., if it has no vertices
    if (igraph::vcount(network) == 0) {
        ## print user warning instead of igraph error
        logging::logwarn("The input network has no vertices. Will return NA right away.")

        ## cancel the execution and return NA
        return(NA)
    }

    mode = match.arg(mode)
    degrees = igraph::degree(network, mode = c(mode))
    vertex = which.max(degrees)
    df = data.frame("name" = names(vertex), "degree" = unname(degrees[vertex]))
    return(df)
}

#' Calculate the average degree of a network.
#'
#' @param network the network to be examined
#' @param mode the mode to be used for determining the degrees [default: "total"]
#'
#' @return The average degree of the vertices in the network.
metrics.avg.degree = function(network, mode = c("total", "in", "out")) {
    mode = match.arg(mode)
    degrees = igraph::degree(network, mode = c(mode))
    avg = mean(degrees)
    return(c(avg.degree = avg))
}

#' Calculate all vertex degrees for the given network
#'
#' @param network the network to be examined
#' @param sort whether the resulting dataframe is to be sorted by the vertex degree [default: TRUE]
#' @param sort.decreasing if sorting is active, this says whether the dataframe is to be
#'                        sorted in descending or ascending order [default: TRUE]
#'
#' @return A dataframe containing the vertices and their respective degrees.
metrics.vertex.degrees = function(network, sort = TRUE, sort.decreasing = TRUE) {
    if (sort) {
        degrees = sort(igraph::degree(network, mode = "total"), decreasing = sort.decreasing)
    } else {
        degrees = igraph::degree(network, mode = "total")
    }
    return(data.frame("name" = names(degrees), "degree" = unname(degrees)))
}

#' Calculate the density of the given network.
#'
#' @param network the network to be examined
#'
#' @return The density of the network.
metrics.density = function(network) {
    density = igraph::graph.density(network)
    return(c(density = density))
}

#' Calculate the average path length for the given network.
#'
#' @param network the network to be examined
#' @param directed whether to consider directed paths in directed networks [default: TRUE]
#' @param unconnected whether there are subnetworks in the network that are not connected.
#'                    If \code{TRUE} only the lengths of the existing paths are considered and averaged;
#'                    if \code{FALSE} the length of the missing paths are counted having length \code{vcount(graph)}, one longer than
#'                    the longest possible geodesic in the network (from igraph documentation) [default: TRUE]
#'
#' @return The average path length of the given network.
metrics.avg.pathlength = function(network, directed = TRUE, unconnected = TRUE) {
    avg.pathlength = igraph::average.path.length(network, directed = directed, unconnected = unconnected)
    return(c(avg.pathlength = avg.pathlength))
}

#' Calculate the average clustering coefficient for the given network.
#'
#' *Note*: The local clustering coefficient is \code{NaN} for all vertices with a degree < 2.
#' Such vertices are removed from all average calculations for any averaging \code{cc.type}.
#'
#' @param network the network to be examined
#' @param cc.type the type of cluserting coefficient to be calculated [default: "global"]
#'
#' @return The clustering coefficient of the network.
metrics.clustering.coeff = function(network, cc.type = c("global", "local", "barrat", "localaverage")) {
    cc.type = match.arg(cc.type)
    cc = igraph::transitivity(network, type = cc.type, vids = NULL)
    return(c(clustering = cc))
}

#' Calculate the modularity metric for the given network.
#'
#' @param network the network to be examined
#' @param community.detection.algorithm the algorithm to be used for the detection of communities
#'            which is required for the calculation of the clustering coefficient [default: igraph::cluster_walktrap]
#'
#' @return The modularity value for the given network.
metrics.modularity = function(network, community.detection.algorithm = igraph::cluster_walktrap) {
    comm = community.detection.algorithm(network)
    mod = igraph::modularity(network, igraph::membership(comm))
    return(c(modularity = mod))
}

#' This function determines whether a network can be considered a
#' small-world network based on a quantitative categorical decision.
#'
#' The procedure used in this function is based on the work "Network
#' 'Small-World-Ness': A Quantitative Method for Determining Canonical
#' Network Equivalence" by Mark D. Humphries and Kevin Gurney [1].
#' [1] http://journals.plos.org/plosone/article?id=10.1371/journal.pone.0002051
#'
#' The algorithm relies on the Erdös-Renyi random network with the same number
#' of vertices and edges as the given network.
#'
#' In order to get a binary (true/false) decision on smallworldness of a network,
#' use \code{metrics.is.smallworld} instead.
#'
#' Important: The given network needs to be simplified for the calculation to work!
#'
#' @param network the simplified network to be examined
#'
#' @return The smallworldness value of the network.
metrics.smallworldness = function(network) {
    ## first check whether the network is simplified
    if (!is.simple(network)) {
        ## if this is not the case, raise an error and stop the execution
        error.message = "The input network has too many edges. Try again with a simplified network."
        logging::error(error.message)
        stop(error.message)
    }

    ## else construct Erdös-Renyi network 'h' with same number of vertices and edges as the given network 'network',
    ## as the requirement of the function is fulfilled
    h = igraph::erdos.renyi.game(n = igraph::vcount(network),
                                 p.or.m = igraph::ecount(network),
                                 type = "gnm",
                                 directed = FALSE)

    ## compute clustering coefficients
    g.cc = igraph::transitivity(network, type = "global")
    h.cc = igraph::transitivity(h, type = "global")
    ## compute average shortest-path length
    g.l = igraph::average.path.length(network, unconnected = TRUE)
    h.l = igraph::average.path.length(h, unconnected = TRUE)

    ## binary decision
    ## intermediate variables
    gamma = g.cc / h.cc
    lambda = g.l / h.l

    ## indicator s.delta
    s.delta = gamma / lambda

    return (c(smallworldness = s.delta))
}

#' Decide, whether a network is smallworld or not.
#'
#' @param network the network to be examined
#'
#' @return \code{TRUE}, if the network is smallworld,
#'         \code{FALSE}, if it is not,
#'         \code{NA}, if an error occured.
metrics.is.smallworld = function(network) {
    s.delta = metrics.smallworldness(network)

    ## return whether the network is smallworld
    return(s.delta > 1)
}


#' Determine scale freeness of a network using the power law fitting method.
#'
#' @param network the network to be examined
#' @param minimum.number.vertices the minimum number of vertices with which
#'  a network can be scale free [default: 30]
#'
#' @return A dataframe containing the different values, connected to scale-freeness.
metrics.scale.freeness = function(network, minimum.number.vertices = 30) {
    v.degree = sort(igraph::degree(network, mode = "total"), decreasing = TRUE)

    ## Power-law fiting
    ## (by  Mitchell Joblin <mitchell.joblin.ext@siemens.com>, Siemens AG,  2012, 2013)
    p.fit = igraph::power.law.fit(v.degree, implementation = "plfit")
    param.names = c("alpha", "xmin", "KS.p")
    res = list()
    res[param.names] = p.fit[param.names]

    ## Check percent of vertices under power-law
    res["num.power.law"] = length(which(v.degree >= res[["xmin"]]))
    res["percent.power.law"] = 100 * (res[["num.power.law"]] / length(v.degree))

    ## If less than minimum.number.vertices vertices are in the power law, set x_min manually
    ## to include a minimum of number of vertices and recompute the powerlaw fit
    non.zero.degree.v.count = length(v.degree[v.degree > 0])
    if(res[["num.power.law"]] < minimum.number.vertices
       & non.zero.degree.v.count >= minimum.number.vertices) {
        ## vertex degree is sorted above
        x.min = v.degree[[minimum.number.vertices]]
        p.fit = power.law.fit(v.degree, implementation = "plfit", xmin = x.min)
        res[param.names] = p.fit[param.names]

        ## Check percent of vertices under power-law
        res[["num.power.law"]] = length(which(v.degree >= res[["xmin"]]))
        res[["percent.power.law"]] = 100 * (res[["num.power.law"]] / length(v.degree))
    }

    ## Remove non conclusive sample sizes
    if(res[["num.power.law"]] < minimum.number.vertices) {
        res[["KS.p"]] = 0 # 0 instead of NA
    }

    df = as.data.frame(res, row.names = "scale.freeness")
    return(df)
}

#' Decide, whether a network is scale free or not.
#'
#' @param network the network to be examined
#' @param minimum.number.vertices the minimum number of vertices with which
#'  a network can be scale free [default: 30]
#'
#' @return \code{TRUE}, if the network is scale free,
#'         \code{FALSE}, otherwise.
metrics.is.scale.free = function(network, minimum.number.vertices = 30) {
    df = metrics.scale.freeness(network, minimum.number.vertices)
    return(df[["KS.p"]] >= 0.05)
}

#' Calculate the hierarchy values for a network, i.e., the vertex degrees and the local
#' clustering coefficient.
#'
#' *Note*: The local clustering coefficient is \code{NaN} for all vertices with a degree < 2.
#'
#' @param network the network to be examined
#'
#' @return a data.frame containing the following columns:
#'         - \code{"deg"}: the vertex degrees for all vertices in the given network,
#'         - \code{"cc"}: the local clustering coefficient for all vertices in the given network, and
#'         - \code{"log.deg"} and \code{"log.cc"}: the logarithmic values for the columns
#'                \code{"deg"} and \code{"cc"}, respectively (see function \code{log})
metrics.hierarchy = function(network) {
    degrees = igraph::degree(network, mode = "total")
    cluster.coeff = igraph::transitivity(network, type = "local", vids = NULL)
    return(data.frame(
        deg = degrees,
        cc = cluster.coeff,
        log.deg = log(degrees),
        log.cc = log(cluster.coeff)
    ))
}


## The column headers for a centrality data frame calculated by the function \code{metrics.vertex.centralities}
VERTEX.CENTRALITIES.COLUMN.NAMES = c("vertex.name", "centrality")

#' Calculate the centrality value for vertices from a network and project data.
#' If a \code{ProjectData} is supplied, only vertices from the network that are also present in the project data are
#' considered. Otherwise, if no custom vector \code{restrict.classification.to.vertices} is supplied, all vertices of
#' the network are considered.
#'
#' @param network the network containing the vertices to classify
#' @param proj.data the \code{ProjectData} containing the authors or artifacts to classify
#' @param type a character string declaring the classification metric. The classification metric determines which
#'             numerical characteristic of vertices is chosen as their centrality value.
#'             The parameter only supports network-based options/metrics:
#'              - "network.degree"
#'              - "network.eigen"
#'              - "network.hierarchy"
#'             [defalt: "network.degree"]
#' @param restrict.classification.to.vertices a vector of vertex names. Only vertices that are contained within this
#'                                            vector are to be classified. Vertices that appear in the vector but are
#'                                            not part of the classification result (i.e., they are not present in the
#'                                            underlying data) will be added to it afterwards (with a centrality value
#'                                            of \code{NA}). \code{NULL} means that the restriction is automatically
#'                                            calculated from the data based on the network's edge relations if and only
#'                                            if both network and data are present. In any other case \code{NULL} will
#'                                            not introduce any further restriction. [default: NULL]
#'
#' @return a data.frame with the columns \code{"vertex.name"} and \code{"centrality"} containing the centrality values
#'         for each respective vertex
metrics.vertex.centralities = function(network,
                                       proj.data,
                                       type = c("network.degree",
                                                "network.eigen",
                                                "network.hierarchy"),
                                       restrict.classification.to.vertices = NULL) {
    type = match.arg(type)

    ## check whether the restrict parameter is set to default 'NULL'
    if (is.null(restrict.classification.to.vertices)) {
        ## now check whether both data and network are present
        if (!is.null(network) && !is.null(proj.data) && igraph::vcount(network) > 0 && igraph::ecount(network) > 0) {
            ## in this case calculate the restrict parameter based on the edge relation along with the vertices from
            ## these data.sources
            sources = get.data.sources.from.relations(network)

            ## first check whether the network only consists of author vertices
            ## therefore get a vector with all vertex types
            vertex.types = unique(igraph::V(network)$type)
            if (vertex.types == TYPE.AUTHOR) {
                ## in this case, use the 'get.authors.by.data.source' function to get the author list
                restrict.classification.to.vertices = proj.data$get.authors.by.data.source(sources)[["author.name"]]
            }
            else if (vertex.types == TYPE.ARTIFACT) {
                ## in this case, always use artifact relation, as both unipartite edges connecting to artifact vertices
                ## as well as bipartite have an artifact relation
                restrict.classification.to.vertices = proj.data$get.artifacts(sources)
            }
            else {
                ## when both vertex types are present, compute both authors and artifacts into one vector
                restrict.authors = proj.data$get.authors.by.data.source(sources)[["author.name"]]
                restrict.artifacts = proj.data$get.artifacts(sources)
                restrict.classification.to.vertices = append(restrict.authors, restrict.artifacts)
            }
        }
        ## else leave the parameter at 'NULL' which still serves as a default value for the
        ## 'get.author.class.by.type' function
    }

    ## calculate the centrality tables
    class = get.author.class.by.type(network = network,
                                     proj.data = proj.data,
                                     type = type,
                                     restrict.classification.to.authors = restrict.classification.to.vertices)

    ## bind the two data frames for core and peripheral together
    centrality = rbind(class[["core"]], class[["peripheral"]])

    ## set column names accordingly
    colnames(centrality) = VERTEX.CENTRALITIES.COLUMN.NAMES

    ## order by centrality (descending) (with NA being at the bottom) and then by name (ascending)
    centrality = centrality[order(-centrality[[ VERTEX.CENTRALITIES.COLUMN.NAMES[[2]] ]],
                                  centrality[[ VERTEX.CENTRALITIES.COLUMN.NAMES[[1]] ]]), ]

    return(centrality)
}
