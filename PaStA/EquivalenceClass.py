"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""


class PropertyList(list):
    """
    Just a list that has an additional property
    """
    def __init__(self, *args, **kwargs):
        list.__init__(self, *args, **kwargs)
        self._property = None

    @property
    def property(self):
        return self._property

    @property.setter
    def property(self, property):
        self._property = property


class EquivalenceClass:
    PROPERTY_SEPARATOR = ' => '

    def __init__(self):
        self.forward_lookup = {}
        self.transitive_list = []

    def insert_single(self, key):
        if key not in self.forward_lookup:
            self.transitive_list.append(PropertyList([key]))
            new_id = len(self.transitive_list) - 1
            self.forward_lookup[key] = new_id

    def insert(self, key1, key2):
        id1 = key1 in self.forward_lookup
        id2 = key2 in self.forward_lookup

        if not id1 and not id2:
            self.transitive_list.append(PropertyList([key1, key2]))
            id = len(self.transitive_list) - 1
            self.forward_lookup[key1] = id
            self.forward_lookup[key2] = id
        elif id1 and id2:
            # Get indices
            id1 = self.forward_lookup[key1]
            id2 = self.forward_lookup[key2]

            # if indices equal, then we have nothing to do
            if id1 != id2:
                # Merge lists
                self.transitive_list[id1] += self.transitive_list[id2]
                # Remove orphaned list
                self.transitive_list[id2] = PropertyList()

                for i in self.transitive_list[id1]:
                    self.forward_lookup[i] = id1
        elif id1:
            id = self.forward_lookup[key1]
            self.transitive_list[id].append(key2)
            self.forward_lookup[key2] = id
        else:
            id = self.forward_lookup[key2]
            self.transitive_list[id].append(key1)
            self.forward_lookup[key1] = id

    def merge(self, other):
        for i in other.transitive_list:
            base = i[0]
            for j in i[1:]:
                self.insert(base, j)
        self.optimize()

    def optimize(self):
        # Get optimized list by filtering orphaned elements
        self.transitive_list = list(filter(None, self.transitive_list))

        # Reset lookup table
        self.forward_lookup = {}

        # Sort inner lists
        for i in self.transitive_list:
            i.sort()
        # Sort outer list
        self.transitive_list.sort()

        # Recreate the forward lookup dictionary
        for i, keylist in enumerate(self.transitive_list):
            for key in keylist:
                self.forward_lookup[key] = i

    def is_related(self, key1, key2):
        if key1 in self.forward_lookup and key2 in self.forward_lookup:
            return self.forward_lookup[key1] == self.forward_lookup[key2]
        return False

    def set_property(self, key, property):
        if key not in self.forward_lookup:
            self.insert_single(key)
        id = self.forward_lookup[key]
        self.set_property_by_id(id, property)

    def set_property_by_id(self, id, property):
        if id < 0:
            raise IndexError('Out of bounds')
        self.transitive_list[id].property = property

    def get_property(self, key):
        id = self.forward_lookup[key]
        return self.get_property_by_id(id)

    def get_property_by_id(self, id):
        if id < 0:
            raise IndexError('Out of bounds')
        return self.transitive_list[id].property

    def get_equivalence_id(self, key):
        if key in self.forward_lookup:
            return self.forward_lookup[key]
        for i in self:
            if i.property and i.property == key:
                return self.forward_lookup[i[0]]
        raise IndexError('Unable to find equivalence id for %s' % key)

    def get_representative_system(self, compare_function):
        """
        Return a complete representative system of the equivalence class

        :param compare_function: a function that compares two elements of an equivalence class
        :return:
        """
        retval = set()
        for equivclass in self.transitive_list:
            if len(equivclass) == 0:
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

    def get_commit_hashes(self, key):
        """
        :param key: commit hash
        :return: Returns a set of all related commit hashes
        """
        id = self.forward_lookup[key]
        return self.get_commit_hashes_by_id(id)

    def get_commit_hashes_by_id(self, id):
        if id < 0:
            raise IndexError('Out of bounds')
        return set(self.transitive_list[id])

    def get_all_commit_hashes(self):
        """
        :return: Returns a set of all commit hashes managed by the object
        """
        retval = []
        for i in self.transitive_list:
            retval += i
        return set(retval)

    def to_file(self, filename):
        # Optimizing before writing keeps uniformity of data
        self.optimize()
        with open(filename, 'w') as f:
            f.write(str(self))
            f.close()

    @staticmethod
    def from_file(filename, must_exist=False):
        retval = EquivalenceClass()

        try:
            with open(filename, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            print('Warning, file ' + filename + ' not found!')
            if must_exist:
                raise
            return retval

        if not (content and len(content)):
            return retval

        # split by linebreak
        content = list(filter(None, content.splitlines()))
        for i in content:
            # Search for property
            property = None
            if EquivalenceClass.PROPERTY_SEPARATOR in i:
                i, property = i.split(EquivalenceClass.PROPERTY_SEPARATOR)

            # split eache line by whitespace
            commit_hashes = i.split(' ')

            # choose first element to be a reference
            base = commit_hashes[0]
            # insert this single reference
            retval.insert_single(base)

            # Set all other elements
            for commit_hash in commit_hashes[1:]:
                retval.insert(base, commit_hash)

            # Set property, if existing
            if property:
                retval.set_property(base, property)

        retval.optimize()
        return retval

    def __iter__(self):
        self.optimize()
        for i in self.transitive_list:
            yield i

    def __str__(self):
        self.optimize()
        retval = ''
        for i in self.transitive_list:
            retval += ' '.join(map(str, i))
            if i.property:
                retval += EquivalenceClass.PROPERTY_SEPARATOR + str(i.property)
            retval += '\n'
        return retval

    def __contains__(self, key):
        return key in self.forward_lookup

    def num_classes(self):
        return len([x for x in self.transitive_list if x])
