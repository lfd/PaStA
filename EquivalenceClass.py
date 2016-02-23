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

    def insert_single(self, key):
        if key not in self.forward_lookup:
            self.transitive_list.append(PropertyList([key]))
            index = len(self.transitive_list) - 1
            self.forward_lookup[key] = index

    def set_property(self, key, property):
        if key not in self.forward_lookup:
            self.insert_single(key)

        index = self.forward_lookup[key]
        self.transitive_list[index].property = property

    def get_property(self, key):
        if key not in self.forward_lookup:
            return None
        index = self.forward_lookup[key]
        return self.transitive_list[index].property

    def get_property_by_id(self, id):
        try:
            return self.transitive_list[id].property
        except IndexError:
            return None

    def insert(self, key1, key2):
        index1 = key1 in self.forward_lookup
        index2 = key2 in self.forward_lookup

        if not index1 and not index2:
            self.transitive_list.append(PropertyList([key1, key2]))
            index = len(self.transitive_list) - 1
            self.forward_lookup[key1] = index
            self.forward_lookup[key2] = index
        elif index1 and index2:
            # Get indices
            index1 = self.forward_lookup[key1]
            index2 = self.forward_lookup[key2]

            # if indices equal, then we have nothing to do
            if index1 != index2:
                # Merge lists
                self.transitive_list[index1] += self.transitive_list[index2]
                # Remove orphaned list
                self.transitive_list[index2] = PropertyList()

                for i in self.transitive_list[index1]:
                    self.forward_lookup[i] = index1
        elif index1:
            index = self.forward_lookup[key1]
            self.transitive_list[index].append(key2)
            self.forward_lookup[key2] = index
        else:
            index = self.forward_lookup[key2]
            self.transitive_list[index].append(key1)
            self.forward_lookup[key1] = index

    def merge(self, other):
        for i in other.transitive_list:
            base = i[0]
            for j in i[1:]:
                self.insert(base, j)
        self.optimize()

    def get_equivalence_id(self, key):
        if key in self.forward_lookup:
            return self.forward_lookup[key]
        return None

    def get_commit_hashes_by_id(self, id):
        try:
            return set(self.transitive_list[id])
        except IndexError:
            return None

    def get_commit_hashes(self, key):
        """
        :param key: commit hash
        :return: Returns a set of all related commit hashes
        """
        retval = set()
        if key in self.forward_lookup:
            index = self.forward_lookup[key]
            retval = set(self.transitive_list[index])
        return retval

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
