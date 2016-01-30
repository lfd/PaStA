import pickle
import sys
import termios
import tty


class TransitiveKeyList:
    def __init__(self):
        self.forward_lookup = {}
        self.transitive_list = []

    def optimize(self):

        # Get optimized list
        filtered_list = list(filter(None, self.transitive_list))

        # Check if optimization is necessary
        if len(self.transitive_list) != len(filtered_list):
            # Reset lookup table
            self.forward_lookup = {}

            # Filter orphaned elements
            self.transitive_list = filtered_list

            # Recreate the forward lookup dictionary
            for i, keylist in enumerate(self.transitive_list):
                for key in keylist:
                    self.forward_lookup[key] = i

    def is_related(self, key1, key2):
        if key1 in self.forward_lookup and key2 in self.forward_lookup:
            return self.forward_lookup[key1] == self.forward_lookup[key2]

        return False

    def insert(self, key1, key2):
        index1 = key1 in self.forward_lookup
        index2 = key2 in self.forward_lookup

        if not index1 and not index2:
            self.transitive_list.append([key1, key2])
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
                self.transitive_list[index2] = []

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

    def to_file(self, filename):
        with open(filename, 'w') as f:
            f.write(str(self))
            f.close()

    def __iter__(self):
        self.optimize()
        for i in self.transitive_list:
            yield i

    def __str__(self):
        return '\n'.join(
                map(lambda x: ' '.join(map(str, x)),
                    filter(None, self.transitive_list)))

    @staticmethod
    def from_file(filename):
        retval = TransitiveKeyList()

        content = file_to_string(filename, must_exist=False)
        if content is not None and len(content):
            # split by linebreak
            content = list(filter(None, content.split('\n')))
            for i in content:
                # split eache line by whitespace
                commit_hashes = i.split(' ')
                if len(commit_hashes) < 2:
                    raise ValueError('Invalid line')

                base = commit_hashes[0]
                for commit_hash in commit_hashes[1:]:
                    retval.insert(base, commit_hash)

        retval.optimize()
        return retval


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def file_to_string(filename, must_exist=True):
    try:
        # Well things are crappy. For decades, encoding has been a real problem
        # Git commits in the linux kernel are messy and sometimes have non-valid encoding
        # Anyway, opening a file as binary and decoding it to iso8859 solves the problem :-)
        with open(filename, 'rb') as f:
            retval = str(f.read().decode('iso8859'))
            f.close()
    except FileNotFoundError:
        print('Warning, file ' + filename + ' not found!')
        if must_exist:
            raise
        return None

    return retval


class DictList(dict):
    def __init__(self, *args):
        dict.__init__(self, *args)

    def to_file(self, filename, human_readable=False):
        if human_readable:
            if len(self) == 0:
                return

            with open(filename, 'w') as f:
                f.write('\n'.join(map(lambda x: str(x[0]) + ' ' + ' '.join(x[1]), self.items())) + '\n')
                f.close()
        else:
            with open(filename + '.pkl', 'wb') as f:
                pickle.dump(self, f, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def from_file(filename, human_readable=False, must_exist=False):
        try:
            if human_readable:
                retval = DictList()
                with open(filename, 'r') as f:
                    for line in f:
                        (key, val) = line.split(' ', 1)
                        retval[key] = list(map(lambda x: x.rstrip('\n'), val.split(' ')))
                    f.close()
                return retval
            else:
                with open(filename + '.pkl', 'rb') as f:
                    return DictList(pickle.load(f))

        except FileNotFoundError:
            if human_readable:
                print('Warning, file ' + filename + ' not found!')
            else:
                print('Warning, file ' + filename + '.pkl not found!')
            if must_exist:
                raise
            return DictList()
