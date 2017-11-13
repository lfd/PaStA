"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from logging import getLogger

log = getLogger(__name__[-15:])


class EquivalenceClass:
    SEPARATOR = ' => '

    def __init__(self):
        self.classes = list()
        self.lookup = dict()
        self.tags = set()

    def optimize(self):
        # get optimized list by filtering orphaned elements
        self.classes = list(filter(None, self.classes))

        # reset lookup table
        self.lookup = dict()

        # recreate the lookup dictionary
        for i, keylist in enumerate(self.classes):
            for key in keylist:
                self.lookup[key] = i

    def remove_class(self, representative):
        id = self.lookup[representative]

        elems = self.classes.pop(id)
        for elem in elems:
            self.lookup.pop(elem)

        for elem in elems:
            self.insert_single(elem)

        return elems

    def is_related(self, *elems):
        """
        Returns True, if _all_ elements are in the same equivalence class
        """
        ids = {self.lookup.get(x, None) for x in elems}

        if None in ids:
            return False

        return len(ids) == 1

    def is_unrelated(self, *elems):
        """
        Returns True, if _all_ elements are in their own class
        """
        num_elems = len(elems)
        ids = [self.lookup.get(x, None) for x in elems]
        num_elems -= ids.count(None)
        ids = set(ids)
        ids.discard(None)

        if len(ids) == num_elems:
            return True
        return False

    def insert_single(self, elem):
        if elem in self.lookup:
            return self.lookup[elem]

        self.classes.append(set([elem]))
        id = len(self.classes) - 1
        self.lookup[elem] = id

        return id

    def _merge_ids(self, *ids):
        new_class = set()
        new_id = min(ids)

        for id in ids:
            for elem in self.classes[id]:
                self.lookup[elem] = new_id
            new_class |= self.classes[id]
            self.classes[id] = set()

        self.classes[new_id] = new_class

        # truncate empty trailing list elements
        while not self.classes[-1]:
            self.classes.pop()

        return new_id

    def insert(self, *elems):
        ids = [self.insert_single(elem) for elem in elems]

        # check if all elements are already in the same class
        if len(set(ids)) == 1:
            return ids[0]

        return self._merge_ids(*ids)

    def get_equivalence_id(self, key):
        return self.lookup[key]

    def tag(self, key, tag=True):
        if tag is True:
            self.tags.add(key)
        else:
            self.tags.discard(key)

    def get_tagged(self, key=None):
        """
        Returns all tagged entries that are related to key.

        If key is not specified, this function returns all tags.
        """
        if key:
            return self.tags.intersection(self.classes[self.lookup[key]])
        return self.tags

    def get_untagged(self, key=None):
        """
        Returns all untagged entries that are related to key.

        If key is not specified, this function returns all untagged.
        """
        if key:
            return self.classes[self.lookup[key]] - self.tags
        return set(self.lookup.keys()) - self.tags

    def has_tag(self, key):
        return key in self.tags

    def __str__(self):
        retval = str()

        untagged_list = [sorted(x) for x in self.iter_untagged()]
        untagged_list.sort()

        for untagged in untagged_list:
            tagged = self.get_tagged(untagged[0])
            retval += ' '.join(sorted([str(x) for x in untagged]))
            if len(tagged):
                retval += EquivalenceClass.SEPARATOR + \
                          ' '.join(sorted([str(x) for x in tagged]))
            retval += '\n'

        return retval

    def get_representative_system(self, compare_function):
        """
        Return a complete representative system of the equivalence class. Only
        untagged entries are considered.

        :param compare_function: a function that compares two elements of an
                                 equivalence class
        """
        retval = set()
        for equivclass in self.iter_untagged():
            equivclass = list(equivclass)
            if not equivclass:
                continue

            if len(equivclass) == 1:
                retval.add(equivclass[0])
                continue

            rep = equivclass[0]
            for element in equivclass[1:]:
                if compare_function(element, rep):
                    rep = element
            retval.add(rep)

        return retval

    def __iter__(self):
        for elem in self.classes:
            if not elem:
                continue
            yield elem

    def iter_untagged(self):
        for elem in self.classes:
            untagged = elem - self.tags
            if not untagged:
                continue
            yield untagged

    def __contains__(self, item):
        return item in self.lookup

    def to_file(self, filename):
        self.optimize()
        with open(filename, 'w') as f:
            f.write(str(self))

    @staticmethod
    def from_file(filename, must_exist=False):
        retval = EquivalenceClass()

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
        content = [(lambda x: (x[0].split(' ') if x[0] else [],
                               x[1].split(' ') if len(x) == 2 else []))
                   (x.split(EquivalenceClass.SEPARATOR))
                   for x in content]

        for untagged, tagged in content:
            retval.insert(*(untagged + tagged))
            for tag in tagged:
                retval.tag(tag)

        return retval
