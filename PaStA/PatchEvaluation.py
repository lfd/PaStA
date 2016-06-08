"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""


import datetime
import functools
import pickle
import shutil
import sys
import termios
import tty

from enum import Enum
from fuzzywuzzy import fuzz
from multiprocessing import Pool, cpu_count
from statistics import mean

from PaStA.PatchStack import Commit, get_commit
from PaStA import repo


class EvaluationType(Enum):
    PatchStack = 1
    Upstream = 2


class SimRating:
    def __init__(self, msg, diff, diff_lines_ratio):
        """
        :param msg: Message rating
        :param diff: Diff rating
        :param diff_lines_ration: Ratio of number of lines shorter diff to longer diff
        """
        self._msg = msg
        self._diff = diff
        self._diff_lines_ratio = diff_lines_ratio

    @property
    def msg(self):
        return self._msg

    @property
    def diff(self):
        return self._diff

    @property
    def diff_lines_ratio(self):
        return self._diff_lines_ratio

    def __lt__(self, other):
        return self.msg + self.diff < other.msg + other.diff


class EvaluationResult(dict):
    """
    An evaluation is a dictionary with a commit hash as key,
    and a list of tuples (hash, SimRating) as value.
    """

    def __init__(self, eval_type, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.universe = set()
        self._eval_type = eval_type

    @property
    def eval_type(self):
        return self._eval_type

    def merge(self, other):
        if self.eval_type != other.eval_type:
            raise ValueError('Unable to merge results of different types')

        # Check if this key already exists in the check_list
        # if yes, then append to the list
        for key, value in other.items():
            if key in self:
                self[key] += value
            else:
                self[key] = value

    def to_file(self, filename):
        # Sort by SimRating
        for i in self.keys():
            self[i].sort(key=lambda x: x[1], reverse=True)

        with open(filename, 'wb') as f:
            pickle.dump(self, f, pickle.HIGHEST_PROTOCOL)

    def set_universe(self, universe):
        self.universe = set(universe)

    @staticmethod
    def from_file(filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)

    def interactive_rating(self, equivalence_class, false_positive_list,
                           thresholds, respect_commitdate=False, upstream_rating=True):
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

        # Convert the dictionary of evaluation results to a sorted list,
        # sorted by its SimRating
        sorted_er = list(self.items())
        sorted_er.sort(key=lambda x: x[1][0][1])

        for orig_commit_hash, candidates in sorted_er:

            if halt_save:
                break

            for cand_commit_hash, sim_rating in candidates:
                # Check if both commit hashes are the same
                if cand_commit_hash == orig_commit_hash:
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

                if sim_rating.diff_lines_ratio < thresholds.diff_lines_ratio:
                    skipped_by_dlr += 1
                    continue

                if respect_commitdate:
                    l = get_commit(orig_commit_hash)
                    r = get_commit(cand_commit_hash)
                    if l.commit_date > r.commit_date:
                        skipped_by_commit_date += 1
                        continue


                # Weight by message_diff_weight
                rating = thresholds.message_diff_weight * sim_rating.msg +\
                         (1-thresholds.message_diff_weight) * sim_rating.diff

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
                    show_commits(orig_commit_hash, cand_commit_hash)
                    print('Length of list of candidates: %d' % len(candidates))
                    print('Rating: %3.2f (%3.2f message and %3.2f diff, diff length ratio: %3.2f)' %
                          (rating, sim_rating.msg, sim_rating.diff, sim_rating.diff_lines_ratio))
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
                    if upstream_rating:
                        equivalence_class.set_property(orig_commit_hash, cand_commit_hash)
                        # Upstream rating can not have multiple candidates. So break after the first match
                        break
                    else:
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


def preevaluate_two_commits(lhash, rhash):
    # We do not need to evaluate equivalent commit hashes, as they are already belong to the same equivalence class
    if lhash == rhash:
        return False

    orig = get_commit(lhash)
    cand = get_commit(rhash)

    # Don't rely on author dates!
    #delta = cand.author_date - orig.author_date
    #if delta.days < 0:
    #    return False

    # Check if patch is a revertion
    if orig.is_revert != cand.is_revert:
        return False

    return preevaluate_two_diffs(orig.diff, cand.diff)


def preevaluate_two_diffs(ldiff, rdiff):
    common_changed_files = len(ldiff.affected.intersection(rdiff.affected))
    return common_changed_files != 0


def rate_diffs(thresholds, ldiff, rdiff):
    levenshteins = []

    for file_identifier, lhunks in ldiff.patches.items():
        if file_identifier in rdiff.patches:
            levenshtein = []
            rhunks = rdiff.patches[file_identifier]

            for l_hunk_heading, lhunk in lhunks.items():
                """
                 When comparing hunks, it is important to use the 'closest hunk' of the right side.
                 The left hunk does not necessarily have to be absolutely similar to the name of the right hunk.
                """

                # Try to find closest hunk match on the right side
                # First, assume that we have no match at all
                r_hunk_heading = None

                # Is the left hunk heading empty?
                if l_hunk_heading == '':
                    # Then search for an empty hunk heading on the right side
                    if '' in rhunks:
                        r_hunk_heading = ''
                else:
                    # This gets the closed levenshtein rating from key against a list of candidate keys
                    closest_match, rating = sorted(
                            map(lambda x: (x, fuzz.token_sort_ratio(l_hunk_heading, x)),
                                rhunks.keys()),
                            key=lambda x: x[1])[-1]
                    if rating >= thresholds.heading * 100:
                        r_hunk_heading = closest_match

                # Only do comparison if we found an corresponding hunk on the right side
                if r_hunk_heading is not None:
                    rhunk = rhunks[r_hunk_heading]
                    if lhunk.deletions and rhunk.deletions:
                        levenshtein.append(fuzz.token_sort_ratio(lhunk.deletions, rhunk.deletions))
                    if lhunk.insertions and rhunk.insertions:
                        levenshtein.append(fuzz.token_sort_ratio(lhunk.insertions, rhunk.insertions))

            if levenshtein:
                levenshteins.append(mean(levenshtein))

    if not levenshteins:
        levenshteins = [0]

    diff_rating = mean(levenshteins) / 100

    return diff_rating


def evaluate_patch_pair(thresholds, lhs, rhs):
    left_message, left_diff = lhs
    right_message, right_diff = rhs

    left_diff_lines = left_diff.lines
    right_diff_lines = right_diff.lines

    diff_lines_ratio = min(left_diff_lines, right_diff_lines) / max(left_diff_lines, right_diff_lines)

    # get rating of message
    msg_rating = fuzz.token_sort_ratio(left_message, right_message) / 100

    # Skip on diff_lines_ratio less than 1%
    if diff_lines_ratio < 0.01:
        return SimRating(msg_rating, 0, diff_lines_ratio)

    # get rating of diff
    diff_rating = rate_diffs(thresholds, left_diff, right_diff)

    return SimRating(msg_rating, diff_rating, diff_lines_ratio)


def evaluate_commit_pair(thresholds, lhs_commit_hash, rhs_commit_hash):
    # Just in case.
    # Actually, patches with the same commit hashes should never be compared, as preevaluate_single_patch will evaluate
    # to False for equivalent commit hashes.
    if lhs_commit_hash == rhs_commit_hash:
        print('Autoreturning on %s' % lhs_commit_hash)
        return SimRating(1, 1, 1)

    lhs_commit = get_commit(lhs_commit_hash)
    rhs_commit = get_commit(rhs_commit_hash)

    return evaluate_patch_pair(thresholds, (lhs_commit.message, lhs_commit.diff), (rhs_commit.message, rhs_commit.diff))


def _preevaluation_helper(candidate_hashes, orig_hash):
    f = functools.partial(preevaluate_two_commits, orig_hash)
    return orig_hash, list(filter(f, candidate_hashes))


def _evaluation_helper(thresholds, l_r, verbose=False):
    left, right = l_r
    if verbose:
        print('Evaluating 1 commit hash against %d commit hashes' % len(right))

    f = functools.partial(evaluate_commit_pair, thresholds, left)
    results = list(map(f, right))
    results = list(zip(right, results))

    # sort SimRating
    results.sort(key=lambda x: x[1], reverse=True)

    return left, results


def evaluate_commit_list(original_hashes, candidate_hashes, eval_type, thresholds,
                         parallelise=False, verbose=False,
                         cpu_factor=1.25):
    """
    Evaluates two list of original and candidate hashes against each other

    :param original_hashes: list of commit hashes
    :param candidate_hashes: list of commit hashes to compare against
    :param parallelise: Parallelise evaluation
    :param verbose: Verbose output
    :param cpu_factor: number of threads to be spawned is the number of CPUs*cpu_factor
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    poolsize = int(cpu_count() * cpu_factor)

    print('Evaluating %d commit hashes against %d commit hashes' % (len(original_hashes), len(candidate_hashes)))

    # Bind candidate hashes to preevaluation
    f_preeval = functools.partial(_preevaluation_helper, candidate_hashes)
    # Bind thresholds to evaluation
    f_eval = functools.partial(_evaluation_helper, thresholds, verbose=True)

    if verbose:
        print('Running preevaluation.')
    if parallelise:
        p = Pool(poolsize)
        preeval_result = p.map(f_preeval, original_hashes)
    else:
        preeval_result = list(map(f_preeval, original_hashes))

    # Filter empty candidates
    preeval_result = dict(filter(lambda x: not not x[1], preeval_result))
    if verbose:
        print('Preevaluation finished.')

    if parallelise:
        result = p.map(f_eval, preeval_result.items())
        p.close()
        p.join()
    else:
        result = list(map(f_eval, preeval_result.items()))

    retval = EvaluationResult(eval_type=eval_type)
    for orig, evaluation in result:
        retval[orig] = evaluation

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


def show_commits(left_hash, right_hash):
    def fix_encoding(string):
        return string.encode('utf-8').decode('ascii', 'ignore')

    def format_message(hash):
        commit = repo[hash]
        message = ['Commit:     %s' % hash,
                   'Author:     %s <%s>' % (fix_encoding(commit.author.name), commit.author.email),
                   'AuthorDate: %s' % datetime.datetime.fromtimestamp(commit.author.time),
                   'Commit:     %s <%s>' % (fix_encoding(commit.committer.name), commit.committer.email),
                   'CommitDate: %s' % datetime.datetime.fromtimestamp(commit.committer.time),
                   ''] + fix_encoding(commit.message).split('\n')
        return message

    def side_by_side(left, right, split_length):
        while len(left) or len(right):
            line = ''
            if len(left):
                line = left.pop(0).expandtabs(6)[0:split_length]
            line = line.ljust(split_length)
            line += ' | '
            if len(right):
                line += right.pop(0).expandtabs(6)[0:split_length]
            print(line)

    left_message = format_message(left_hash)
    right_message = format_message(right_hash)

    left_diff = Commit.get_diff(left_hash).split('\n')
    right_diff = Commit.get_diff(right_hash).split('\n')

    columns, _ = shutil.get_terminal_size()
    maxlen = int((columns-3)/2)

    split_length = max(map(len, left_diff + left_message))
    if split_length > maxlen:
        split_length = maxlen

    sys.stdout.write('\x1b[2J\x1b[H')
    side_by_side(left_message, right_message, split_length)
    print('-' * (split_length+1) + '+' + '-' * (columns-split_length-2))
    side_by_side(left_diff, right_diff, split_length)
