import pickle
from subprocess import call
import sys
import termios
import tty

from config import *


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


class TransitiveKeyList:

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
        retval = TransitiveKeyList()

        content = file_to_string(filename, must_exist=must_exist)
        if content and len(content):
            # split by linebreak
            content = list(filter(None, content.splitlines()))
            for i in content:
                # Search for property
                property = None
                if TransitiveKeyList.PROPERTY_SEPARATOR in i:
                    i, property = i.split(TransitiveKeyList.PROPERTY_SEPARATOR)

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
                retval += TransitiveKeyList.PROPERTY_SEPARATOR + str(i.property)
            retval += '\n'
        return retval

    def __contains__(self, key):
        return key in self.forward_lookup


class DictList(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def to_file(self, filename):
        if len(self) == 0:
            return

        with open(filename, 'w') as f:
            f.write('\n'.join(map(lambda x: str(x[0]) + ' ' + ' '.join(x[1]), self.items())) + '\n')
            f.close()

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
                with open(filename, 'rb') as f:
                    return DictList(pickle.load(f))

        except FileNotFoundError:
            print('Warning, file ' + filename + ' not found!')
            if must_exist:
                raise
            return DictList()


class EvaluationResult(dict):
    """
    An evaluation is a dictionary with a commit hash as key,
    and a list of 3-tuples (hash, msg_rating, diff_rating, diff-length-ratio) as value.

    Check if this key already exists in the check_list, if yes, then append to the list
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def merge(self, other):
        for key, value in other.items():
            # Skip empty evaluation lists
            if not value:
                continue

            if key in self:
                self[key] += value
            else:
                self[key] = value

            self[key].sort(key=lambda x: x[1], reverse=True)

    def to_file(self, filename):
        with open(filename, 'wb') as f:
            pickle.dump(self, f, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def from_file(filename):
        with open(filename, 'rb') as f:
            return EvaluationResult(pickle.load(f))

    def interactive_rating(self, transitive_list, false_positive_list,
                           autoaccept_threshold, interactive_threshold, diff_length_threshold):

        already_false_positive = 0
        already_detected = 0
        auto_accepted = 0
        auto_declined = 0
        accepted = 0
        declined = 0
        skipped = 0
        skipped_by_dlr = 0

        for orig_commit_hash, candidates in self.items():
            for candidate in candidates:
                cand_commit_hash, msg_rating, diff_rating, diff_length_ratio = candidate

                # Check if both commit hashes are the same
                if cand_commit_hash == orig_commit_hash:
                    print('Go back and check your implementation!')
                    continue

                # Check if patch is already known as false positive
                if orig_commit_hash in false_positive_list and \
                   cand_commit_hash in false_positive_list[orig_commit_hash]:
                    already_false_positive += 1
                    continue

                # Check if those two patches are already related
                if transitive_list.is_related(orig_commit_hash, cand_commit_hash):
                    already_detected += 1
                    continue

                if diff_length_ratio < diff_length_threshold:
                    skipped_by_dlr += 1
                    continue

                # Autoaccept if 100% diff match and at least 10% msg match
                if False and diff_rating == 1.0 and msg_rating > 0.1:
                    rating = 1.2
                else:
                    # Rate msg and diff by 0.4/0.8
                    rating = 0.4 * msg_rating + 0.8 * diff_rating

                # Maybe we can autoaccept the patch?
                if rating > autoaccept_threshold:
                    auto_accepted += 1
                    yns = 'y'
                # or even automatically drop it away?
                elif rating < interactive_threshold:
                    auto_declined += 1
                    continue
                # Nope? Then let's do an interactive rating by a human
                else:
                    yns = ''
                    compare_hashes(REPO_LOCATION, orig_commit_hash, cand_commit_hash)
                    print('Length of list of candidates: ' + str(len(candidates)))
                    print('Rating: ' + str(rating) + ' (' + str(msg_rating) + ' message and ' +
                          str(diff_rating) + ' diff, diff length ratio: ' +
                          str(diff_length_ratio) + ')')
                    print('(y)ay or (n)ay or (s)kip?')

                if yns not in ['y', 'n', 's']:
                    while yns not in ['y', 'n', 's']:
                        yns = getch()
                        if yns == 'y':
                            accepted += 1
                        elif yns == 'n':
                            declined += 1
                        elif yns == 's':
                            skipped += 1

                if yns == 'y':
                    transitive_list.insert(orig_commit_hash, cand_commit_hash)
                elif yns == 'n':
                    if orig_commit_hash in false_positive_list:
                        false_positive_list[orig_commit_hash].append(cand_commit_hash)
                    else:
                        false_positive_list[orig_commit_hash] = [cand_commit_hash]

        print('\n\nSome statistics:')
        print(' Interactive Accepted: ' + str(accepted))
        print(' Automatically accepted: ' + str(auto_accepted))
        print(' Interactive declined: ' + str(declined))
        print(' Automatically declined: ' + str(auto_declined))
        print(' Skipped: ' + str(skipped))
        print(' Skipped due to previous detection: ' + str(already_detected))
        print(' Skipped due to false positive mark: ' + str(already_false_positive))
        print(' Skipped by diff length ratio mismatch: ' + str(skipped_by_dlr))


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


def compare_hashes(repo_location, orig_commit_hash, cand_commit_hash):
    call(['./compare_hashes.sh', repo_location, orig_commit_hash, cand_commit_hash])


def group(l, predicate):
    retval = []

    index = 0
    while index < len(l):
        elem = l[index]
        if predicate(elem):
            retval.append([elem])
        else:
            retval[-1].append(elem)
        index += 1

    return retval
