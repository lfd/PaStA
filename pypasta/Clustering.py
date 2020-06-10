"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from logging import getLogger

log = getLogger(__name__[-15:])


class Clustering:
    SEPARATOR = '=>'

    def __init__(self):
        self.clusters = list()
        self.lookup = dict()
        self.upstream = set()

    def optimize(self):
        # get optimized list by filtering orphaned elements
        self.clusters = list(filter(None, self.clusters))

        # reset lookup table
        self.lookup = dict()

        # recreate the lookup dictionary
        for i, keylist in enumerate(self.clusters):
            for key in keylist:
                self.lookup[key] = i

    def ripup_cluster(self, representative):
        """
        Rips up a cluster. This removes all connections of the elements of the
        cluster and reinserts them as single-element clusters
        :return: Elements of the former cluster
        """
        id = self.lookup[representative]

        elems = self.clusters.pop(id)
        for elem in elems:
            self.lookup.pop(elem)

        for elem in elems:
            self.insert_element(elem)

        return elems

    def is_related(self, *elems):
        """
        Returns True, if _all_ elements are in the same cluster
        """
        ids = {self.lookup.get(x, None) for x in elems}

        if None in ids:
            return False

        return len(ids) == 1

    def remove_element(self, elem):
        """
        Remove a single element from its cluster
        """
        self.upstream.discard(elem)
        id = self.lookup.pop(elem)
        self.clusters[id].remove(elem)

    def insert_element(self, elem):
        """
        Assigns elem to a new cluster. Returns the new ID of the cluster. If
        elem is already existent and assigned to a cluster, do nothing but
        return the ID of the cluster.
        """
        if elem in self.lookup:
            return self.lookup[elem]

        self.clusters.append(set([elem]))
        id = len(self.clusters) - 1
        self.lookup[elem] = id

        return id

    def _merge_clusters(self, *ids):
        new_class = set()
        new_id = min(ids)

        for id in ids:
            for key in self.clusters[id]:
                self.lookup[key] = new_id
            new_class |= self.clusters[id]
            self.clusters[id] = set()

        self.clusters[new_id] = new_class

        # truncate empty trailing list elements
        while not self.clusters[-1]:
            self.clusters.pop()

        return new_id

    def insert(self, *elems):
        """
        Create a new cluster with elements elems.
        """
        if len(elems) == 0:
            return

        ids = [self.insert_element(elem) for elem in elems]

        # check if all elements are already in the same class
        if len(set(ids)) == 1:
            return ids[0]

        return self._merge_clusters(*ids)

    def get_cluster_id(self, key):
        return self.lookup[key]

    def mark_upstream(self, key, is_upstream=True):
        if is_upstream is True:
            self.upstream.add(key)
        else:
            self.upstream.discard(key)

    def get_all_elements(self):
        """
        Returns all elements as a set. This includes both, upstream and
        downstream.
        """
        return set(self.lookup.keys())

    def get_cluster(self, elem):
        """
        Given elem, this function returns all elements of the cluster as a set.
        This includes both, upstram and downstream.
        """
        if elem not in self:
            return None
        id = self.get_cluster_id(elem)
        return self.clusters[id].copy()

    def get_upstream(self, elem=None):
        """
        Returns all upstream entries that are related to elem. If elem is not
        specified, this function returns all upstream patches.
        """
        if elem:
            return self.upstream.intersection(self.clusters[self.lookup[elem]])
        return self.upstream

    def get_downstream(self, elem=None):
        """
        Returns all downstream entries that are related to elem. If elem is not
        specified, this function returns all downstream patches.
        """
        if elem:
            return self.clusters[self.lookup[elem]] - self.upstream
        return set(self.lookup.keys()) - self.upstream

    def __getitem__(self, item):
        return self.get_cluster(item)

    def __len__(self):
        return len(self.clusters)

    def __str__(self):
        retval = str()

        cluster_list = [(sorted(downstream), sorted(upstream)) for
                        downstream, upstream in self.iter_split()]

        downstream_list = sorted(filter(lambda x: len(x[0]), cluster_list))
        upstream_list = sorted(
                            [x[1] for x in
                             filter(lambda x: len(x[0]) == 0, cluster_list)])

        for downstreams, upstreams in downstream_list:
            # Convert to string representation. In this way, we can also handle other
            # types than pure strings, like integers.
            downstreams = [str(x) for x in downstreams]
            upstreams = [str(x) for x in upstreams]

            retval += ' '.join(downstreams)
            if len(upstreams):
                retval += ' %s %s' % (Clustering.SEPARATOR, ' '.join(upstreams))
            retval += '\n'

        for upstreams in upstream_list:
            retval += '%s %s\n' % (Clustering.SEPARATOR, ' '.join(upstreams))

        return retval

    def get_representative_system(self, compare_function):
        """
        Return a complete representative system of the equivalence class. Only
        downstream entries are considered.

        :param compare_function: a function that compares two elements of an
                                 equivalence class
        """
        retval = set()
        for cluster, _ in self.iter_split():
            if len(cluster) == 0:
                continue

            cluster = list(cluster)
            if not cluster:
                continue

            if len(cluster) == 1:
                retval.add(cluster[0])
                continue

            rep = cluster[0]
            for element in cluster[1:]:
                if compare_function(element, rep):
                    rep = element
            retval.add(rep)

        return retval

    def __iter__(self):
        # iterate over all classes, and return all items
        for elem in self.clusters:
            if not elem:
                continue
            yield elem

    def iter_split(self):
        """
        Iterate over all clusters. Per cluster, return a tuple of
        (downstream, upstream) patches
        """
        for cluster in self.clusters:
            downstream = cluster - self.upstream
            upstream = cluster & self.upstream
            if len(downstream) == 0 and len(upstream) == 0:
                continue
            yield downstream, upstream

    def __contains__(self, item):
        return item in self.lookup

    def to_file(self, filename):
        self.optimize()
        with open(filename, 'w') as f:
            f.write(str(self))

    @staticmethod
    def from_file(filename, must_exist=False):
        def split_elements(elems):
            return list(filter(None, elems.split(' ')))

        retval = Clustering()

        try:
            with open(filename, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            log.warning('Equivalence class not found: %s' % filename)
            if must_exist:
                raise
            return retval

        if not (content and len(content)):
            return retval

        content = list(filter(None, content.splitlines()))
        for line in content:
            line = line.split(Clustering.SEPARATOR)
            # Append empty upstream list, if not present
            if len(line) == 1:
                line.append('')

            downstream, upstream = split_elements(line[0]), \
                                   split_elements(line[1])

            retval.insert(*(downstream + upstream))
            for element in upstream:
                retval.mark_upstream(element)

        return retval
