#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) University of Passau, 2021

Authors:
   Thomas Kirz <thomas.kirz@gmail.com>
   Pia Eichinger <pia.eichinger@hotmail.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import argparse
import os
import re

CLUSTER_REGEX = re.compile(r'(cluster[0-9]*)\[draw,circle] // \[simple necklace layout] {(.*)};')
EDGE_REGEX = re.compile(r'(cluster[0-9]*)-- (cluster[0-9]*)')

class Cluster():
    def __init__(self, cluster_name, cluster_body, x, y, custom_sep=False, sep=0, layout=""):
        self.cluster_name = cluster_name
        self.cluster_body = cluster_body
        self.x = x
        self.y = y
        self.custom_sep = custom_sep
        self.sep = sep
        self.layout = layout

class Edge():
    def __init__(self, head, tail):
        self.head = head
        self.tail = tail

def xen_routine(lines):
    clusters = []
    edges = []

    # read and save the clusters and add manual modifications
    # cluster1
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=9.5, y=-4.5, layout="spring layout, node distance=40"))

    # cluster2
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    cluster2_body = cluster_match.group(2)
    cluster2_body = cluster2_body.replace("\"x86 architecture\"-- \"efi\"",
                                    "\"efi\"-- \"x86 architecture\"")
    cluster2_body = cluster2_body.replace("\"x86 architecture\"-- \"intel(r) trusted\\nexecution technology (txt)\"",
                                    "\"intel(r) trusted\\nexecution technology (txt)\"--[orient=|] \"x86 architecture\"")
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster2_body, x=-1, y=4, custom_sep=True, sep=-25, layout="spring electrical layout, electric charge=30"))

    # cluster3
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=3, y=-4, layout="simple necklace layout"))

    # cluster4
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=9, y=5.5, custom_sep=True, sep=-10, layout="spring electrical layout, electric charge=5"))

    # cluster5
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=7.5, y=-0.2, layout="simple necklace layout"))

    # read and save the edges
    while lines and EDGE_REGEX.match(lines[0]):
        edge_match = EDGE_REGEX.match(lines.pop(0))
        edges.append(Edge(edge_match.group(1), edge_match.group(2)))

    # modifications to all clusters
    for cluster in clusters:
        # replace '\n' with '\\' and '_' with '\_'
        cluster.cluster_body = cluster.cluster_body.replace("\\n", "\\\\").replace("_", "\\_")

    return clusters, edges


def uboot_routine(lines):
    clusters = []
    edges = []

    # cluster1
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    cluster1_body = cluster_match.group(2)
    # move edge to beginning of body
    cluster1_body = "\"arm zynqmp\"-- \"arm zynq\", " + cluster1_body.replace("\"arm zynqmp\"-- \"arm zynq\", ", "")
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster1_body, x=-8, y=9, custom_sep=True, sep=-10, layout="simple necklace layout"))

    # cluster2
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=0, y=0, custom_sep=True, sep=-7, layout="simple necklace layout"))

    # cluster3
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=-15, y=3, custom_sep=True, sep=-4, layout="simple necklace layout"))

    # cluster4
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=0, y=-12, custom_sep=True, sep=0, layout="simple necklace layout"))

    # cluster5
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    cluster5_body = cluster_match.group(2)
    cluster5_body = cluster5_body.replace("\"ubi\"-- \"arm stm stm32mp\"",
                                          "\"ubi\"[nudge left=200]-- \"arm stm stm32mp\"")
    cluster5_body = cluster5_body.replace("\"arm amlogic\\nsoc support\"-- \"arm\"",
                                          "\"arm amlogic\\nsoc support\"[nudge left=20]-- \"arm\"")
    cluster5_body = cluster5_body.replace("\"power\"-- \"arm amlogic\\nsoc support\"",
                                          "\"power\"[nudge left=83]-- \"arm amlogic\\nsoc support\"")
    cluster5_body = cluster5_body.replace("\"arm stm stm32mp\"-- \"arm\"",
                                          "\"arm stm stm32mp\"[nudge left=40]-- \"arm\"")
    cluster5_body = cluster5_body.replace("\"arm snapdragon\"-- \"arm\"",
                                          "\"arm snapdragon\"[nudge up=5]-- \"arm\"")
    # cluster5_body = cluster5_body.replace("\"arm stm stm32mp\"-- \"arm\"",
    #                                       "\"arm stm stm32mp\"[nudge up=30]-- \"arm\"")
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster5_body, x=-10, y=-7, custom_sep=True, sep=-30, layout="spring electrical layout, electric charge=100"))

    # cluster6
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=1, y=10, custom_sep=True, sep=0, layout="simple necklace layout"))

    # cluster7
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=2, y=-7, custom_sep=True, sep=-5, layout="simple necklace layout"))

    # cluster8
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=-5, y=1.7, layout="simple necklace layout"))

    # cluster9
    cluster_match = CLUSTER_REGEX.match(lines.pop(0))
    clusters.append(Cluster(cluster_name=cluster_match.group(1), cluster_body=cluster_match.group(2), x=3, y=5, layout="simple necklace layout"))

    # read and save the edges
    while lines and EDGE_REGEX.match(lines[0]):
        edge_match = EDGE_REGEX.match(lines.pop(0))
        head = edge_match.group(1)
        tail = edge_match.group(2)

        # only save edges that are connected to clusters in this graph
        if head in (cluster.cluster_name for cluster in clusters) and tail in (cluster.cluster_name for cluster in clusters):
            # edge modifications
            if head == "cluster1" and tail == "cluster4":
                head = "cluster1.120"
            if head == "cluster4" and tail == "cluster1":
                tail = "cluster1.120"

            edges.append(Edge(head, tail))

    # modifications to all clusters
    for cluster in clusters:
        # replace '\n' with '\\' and '_' with '\_'
        cluster.cluster_body = cluster.cluster_body.replace("\\n", "\\\\").replace("_", "\\_")

    return clusters, edges


def main():
    parser = argparse.ArgumentParser(description = "xen .tex file reproducer")
    parser.add_argument("--file", type=str, help="path to input tex file", required=True)
    parser.add_argument("--output", type=str, help="path to output file", required=True)

    args = parser.parse_args()
    file_path = args.file

    file_handle = open(file_path, 'r')
    lines = file_handle.readlines()

    clusters, edges = None, None

    if os.path.basename(file_path).startswith("RELEASE"): # xen
        clusters, edges = xen_routine(lines)
    else: # u-boot
        clusters, edges = uboot_routine(lines)

    # opening the output path in written mode, name of file_handle is 'f'
    with open(args.output, 'w') as f:
        f.write("\\begin{tikzpicture}[\n")
        f.write("    subgraph text top=text centered,\n")
        f.write("    cluster/.style={font=\\small},\n")
        f.write("    ]\n\n")

        # write the clusters
        for cluster in clusters:
            if cluster.custom_sep:
                f.write("\\node[draw,circle,cluster,inner sep=%d] (%s) at (%.1f,%.1f) {\n" % (cluster.sep, cluster.cluster_name, cluster.x, cluster.y))
            else:
                f.write("\\node[draw,circle,cluster] (%s) at (%.1f,%.1f) {\n" % (cluster.cluster_name, cluster.x, cluster.y))
            f.write("    \\tikz[every node/.style={rectangle,inner sep=0,align=center}]\\graph[%s] {\n" % cluster.layout)
            f.write("        %s\n" % cluster.cluster_body)
            f.write("    };\n")
            f.write("};\n\n")

        # write the edges
        for edge in edges:
            f.write("\\draw (%s) edge (%s);\n" % (edge.head, edge.tail))

        f.write("\\end{tikzpicture}")


if __name__ == '__main__':
    ret = main()
