import functools
from fuzzywuzzy import fuzz
from math import ceil
from multiprocessing import Pool, cpu_count
import pickle
from statistics import mean
from subprocess import call
import sys
import termios
import tty

from PaStA.PatchStack import get_commit
from PaStA import config


class Thresholds:
    def __init__(self, autoaccept, interactive, diff_length):
        self.autoaccept = autoaccept
        self.interactive = interactive
        self.diff_length = diff_length


class EvaluationResult(dict):
    """
    An evaluation is a dictionary with a commit hash as key,
    and a list of 3-tuples (hash, msg_rating, diff_rating, diff-length-ratio) as value.
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.universe = set()

    def merge(self, other):
        # Check if this key already exists in the check_list
        # if yes, then append to the list
        for key, value in other.items():
            if key in self:
                self[key] += value
            else:
                self[key] = value

            self[key].sort(key=lambda x: x[1], reverse=True)

    def to_file(self, filename):
        with open(filename, 'wb') as f:
            pickle.dump(self, f, pickle.HIGHEST_PROTOCOL)

    def set_universe(self, universe):
        self.universe = set(universe)

    @staticmethod
    def from_file(filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)

    def interactive_rating(self, equivalence_class, false_positive_list,
                           thresholds, respect_commitdate=False):

        already_false_positive = 0
        already_detected = 0
        auto_accepted = 0
        auto_declined = 0
        accepted = 0
        declined = 0
        skipped = 0
        skipped_by_dlr = 0
        skipped_by_commit_date = 0

        halt_save = False

        for i in self.universe:
            equivalence_class.insert_single(i)

        for orig_commit_hash, candidates in self.items():

            if halt_save:
                break

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
                if equivalence_class.is_related(orig_commit_hash, cand_commit_hash):
                    already_detected += 1
                    continue

                if diff_length_ratio < thresholds.diff_length:
                    skipped_by_dlr += 1
                    continue

                if respect_commitdate:
                    l = get_commit(orig_commit_hash)
                    r = get_commit(cand_commit_hash)
                    if l.commit_date > r.commit_date:
                        skipped_by_commit_date += 1
                        continue

                # Overall rating is 0, if diff_rating is 0
                if diff_rating == 0:
                    rating = 0
                # Autoaccept if 100% diff match and at least 10% msg match
                elif False and diff_rating == 1.0 and msg_rating > 0.1:
                    rating = 1.0
                else:
                    # Rate msg and diff by (1/3)/(2/3)
                    rating = msg_rating / 3 + 2 *  diff_rating / 3

                # Maybe we can autoaccept the patch?
                if rating >= thresholds.autoaccept:
                    auto_accepted += 1
                    yns = 'y'
                # or even automatically drop it away?
                elif rating < thresholds.interactive:
                    auto_declined += 1
                    continue
                # Nope? Then let's do an interactive rating by a human
                else:
                    yns = ''
                    compare_hashes(orig_commit_hash, cand_commit_hash)
                    print('Length of list of candidates: %d' % len(candidates))
                    print('Rating: %3.2f (%3.2f message and %3.2f diff, diff length ratio: %3.2f)' %
                          (rating, msg_rating, diff_rating, diff_length_ratio))
                    print('(y)ay or (n)ay or (s)kip?  To abort: halt and (d)iscard, (h)alt and save')

                if yns not in {'y', 'n', 's', 'd', 'h'}:
                    while yns not in {'y', 'n', 's', 'd', 'h'}:
                        yns = getch()
                        if yns == 'y':
                            accepted += 1
                        elif yns == 'n':
                            declined += 1
                        elif yns == 's':
                            skipped += 1
                        elif yns == 'd':
                            quit()
                        elif yns == 'h':
                            halt_save = True
                            break

                if yns == 'y':
                    equivalence_class.insert(orig_commit_hash, cand_commit_hash)
                elif yns == 'n':
                    if orig_commit_hash in false_positive_list:
                        false_positive_list[orig_commit_hash].append(cand_commit_hash)
                    else:
                        false_positive_list[orig_commit_hash] = [cand_commit_hash]

        equivalence_class.optimize()

        print('\n\nSome statistics:')
        print(' Interactive Accepted: ' + str(accepted))
        print(' Automatically accepted: ' + str(auto_accepted))
        print(' Interactive declined: ' + str(declined))
        print(' Automatically declined: ' + str(auto_declined))
        print(' Skipped: ' + str(skipped))
        print(' Skipped due to previous detection: ' + str(already_detected))
        print(' Skipped due to false positive mark: ' + str(already_false_positive))
        print(' Skipped by diff length ratio mismatch: ' + str(skipped_by_dlr))
        if respect_commitdate:
            print(' Skipped by commit date mismatch: ' + str(skipped_by_commit_date))


class DictList(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def to_file(self, filename):
        if len(self) == 0:
            return

        with open(filename, 'w') as f:
            f.write('\n'.join(map(lambda x: str(x[0]) + ' ' + ' '.join(sorted(x[1])), sorted(self.items()))) + '\n')
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


def preevaluate_single_patch(original_hash, candidate_hash):
    orig = get_commit(original_hash)
    cand = get_commit(candidate_hash)

    if original_hash == candidate_hash:
        return False

    delta = cand.author_date - orig.author_date
    if delta.days < 0:
        return False

    # Check if patch is a revertion
    if orig.is_revert != cand.is_revert:
        return False

    # Filtert auch merge commits
    common_changed_files = len(orig.affected.intersection(cand.affected))
    if common_changed_files == 0:
        return False

    return True


def evaluate_single_patch(original_hash, candidate_hash):

    orig = get_commit(original_hash)
    cand = get_commit(candidate_hash)

    left_diff_length = orig.diff_length
    right_diff_length = cand.diff_length

    diff_length_ratio = min(left_diff_length, right_diff_length) / max(left_diff_length, right_diff_length)

    # traverse through the left patch
    levenshteins = []
    for file_identifier, lhunks in orig.diff.items():
        if file_identifier in cand.diff:
            levenshtein = []
            rhunks = cand.diff[file_identifier]

            for l_key, (l_removed, l_added) in lhunks.items():
                """
                 When comparing hunks, it is important to use the 'closest hunk' of the right side.
                 The left hunk does not necessarily have to be absolutely similar to the name of the right hunk.
                """

                r_key = None
                if l_key == '':
                    if '' in rhunks:
                        r_key = ''
                else:
                    # This gets the closed levenshtein rating from key against a list of candidate keys
                    closest_match, rating = sorted(
                            map(lambda x: (x, fuzz.token_sort_ratio(l_key, x)),
                                rhunks.keys()),
                            key=lambda x: x[1])[-1]
                    if rating > 60:
                        r_key = closest_match

                if r_key is not None:
                    r_removed, r_added = rhunks[r_key]
                    if l_removed and r_removed:
                        levenshtein.append(fuzz.token_sort_ratio(l_removed, r_removed))
                    if l_added and r_added:
                        levenshtein.append(fuzz.token_sort_ratio(l_added, r_added))

            if levenshtein:
                levenshteins.append(mean(levenshtein))

    if not levenshteins:
        levenshteins = [0]

    diff_rating = mean(levenshteins) / 100

    # get rating of message
    msg_rating = fuzz.token_sort_ratio(orig.message, cand.message) / 100

    return candidate_hash, msg_rating, diff_rating, diff_length_ratio


def _preevaluation_helper(candidate_hashes, orig_hash):
    f = functools.partial(preevaluate_single_patch, orig_hash)
    return orig_hash, list(filter(f, candidate_hashes))


def evaluate_patch_list(original_hashes, candidate_hashes,
                        parallelize=False, verbose=False,
                        cpu_factor=1.25):
    """
    Evaluates two list of original and candidate hashes against each other

    :param original_hashes: original patches
    :param candidate_hashes: potential candidates
    :param parallelize: Parallelize evaluation
    :param verbose: Verbose output
    :param cpu_factor: number of threads to be spawned is the number of CPUs*cpu_factor
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    retval = EvaluationResult()
    num_threads = int(cpu_count() * cpu_factor)

    print('Evaluating %d commit hashes against %d commit hashes' % (len(original_hashes), len(candidate_hashes)))

    if verbose:
        print('Running preevaluation.')
    f = functools.partial(_preevaluation_helper, candidate_hashes)
    if parallelize:
        p = Pool(num_threads)
        preeval_result = p.map(f, original_hashes)
        p.close()
        p.join()
    else:
        preeval_result = list(map(f, original_hashes))
    # Filter empty candidates
    preeval_result = dict(filter(lambda x: not not x[1], preeval_result))
    if verbose:
        print('Preevaluation finished.')

    for i, commit_hash in enumerate(original_hashes):
        if verbose:
            sys.stdout.write('\r Evaluating %d/%d' % (i+1, len(original_hashes)))

        # Do we have to consider the commit_hash?
        if commit_hash not in preeval_result:
            continue

        this_candidate_hashes = preeval_result[commit_hash]
        f = functools.partial(evaluate_single_patch, commit_hash)

        if parallelize and len(this_candidate_hashes) > 5*num_threads:
            chunksize = ceil(len(this_candidate_hashes) / num_threads)
            pool = Pool(num_threads)
            result = pool.map(f, this_candidate_hashes, chunksize=chunksize)
            pool.close()
            pool.join()
        else:
            result = list(map(f, this_candidate_hashes))

        # Drop None values
        result = list(filter(None, result))

        # sort by ratio
        result.sort(key=lambda x: x[1], reverse=True)

        retval[commit_hash] = result

    if verbose:
        sys.stdout.write('\n')

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


def compare_hashes(orig_commit_hash, cand_commit_hash):
    call(['./compare_hashes.sh', config.repo, orig_commit_hash, cand_commit_hash])
