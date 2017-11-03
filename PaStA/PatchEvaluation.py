"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import functools
import os
import pickle

from enum import Enum
from fuzzywuzzy import fuzz
from multiprocessing import Pool, cpu_count
from logging import getLogger
from statistics import mean

from .Util import *

log = getLogger(__name__[-15:])

# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None


class EvaluationType(Enum):
    PatchStack = 1
    Upstream = 2


class FalsePositives:
    FILENAMES = {
        EvaluationType.PatchStack: 'patch-stack',
        EvaluationType.Upstream: 'upstream',
    }

    def __init__(self, is_mbox, type, dir=None, must_exist=False):
        self._type = type
        self._is_dict = type != EvaluationType.PatchStack
        self._false_positives = {} if self._is_dict else []
        self._prefix = 'mbox-' if is_mbox else ''

        if dir:
            filename = os.path.join(dir, self._prefix +
                                    FalsePositives.FILENAMES[type])
            if not os.path.isfile(filename):
                if must_exist:
                    raise FileNotFoundError(filename)
                else:
                    log.warning('false-positive file not found: %s' % filename)
                return
        with open(filename, 'r') as f:
            for line in f:
                line = line.rstrip('\n').split(' ')
                if self._is_dict:
                    first = line[0]
                    rest = line[1:]
                    self._false_positives[first] = set(rest)
                else:
                    self._false_positives.append(set(line))

    def to_file(self, directory):
        if len(self._false_positives) == 0:
            return

        if not os.path.exists(directory):
            os.makedirs(directory)
        fp_filename = os.path.join(directory, self._prefix +
                                   FalsePositives.FILENAMES[self._type])

        with open(fp_filename, 'w') as f:
            if self._is_dict:
                for key in sorted(self._false_positives.keys()):
                    values = sorted(self._false_positives[key])
                    f.write('%s %s\n' % (key, ' '.join(values)))
            else:
                sorted_fp = sorted([sorted(x) for x in self._false_positives])
                for line in sorted_fp:
                    f.write('%s\n' % ' '.join(line))

    def mark(self, equivalence_class, left, right):
        if self._is_dict:
            if left not in self._false_positives:
                self._false_positives[left] = set()
            self._false_positives[left].add(right)
        else:
            l_group = equivalence_class.get_equivalence_id(left)
            r_group = equivalence_class.get_equivalence_id(right)
            succ = False
            for i in self._false_positives:
                id_set = {equivalence_class.get_equivalence_id(x) for x in i}
                if l_group in id_set:
                    i |= set([right])
                    succ = True
                if r_group in id_set:
                    i |= set([left])
                    succ = True
                if succ:
                    break
            if not succ:
                self._false_positives.append(set([left, right]))

    def is_false_positive(self, equivalence_class, left, right):
        if self._is_dict:
            if left in self._false_positives and right in self._false_positives[left]:
                return True
            return False
        else:
            l_group = equivalence_class.get_equivalence_id(left)
            r_group = equivalence_class.get_equivalence_id(right)

            for i in self._false_positives:
                i = {equivalence_class.get_equivalence_id(x) for x in i}
                if l_group in i and r_group in i:
                    return True
            return False

    def check_consistency(self, equivalence_class):
        print_banner = True

        def banner(banner):
            nonlocal print_banner
            if print_banner:
                print(banner)
            print_banner = False

        if self._is_dict:
            for origin, false_positives in self._false_positives.items():
                for fp in false_positives:
                    if origin in equivalence_class and \
                        fp in equivalence_class.get_tagged(origin):
                        banner('Inconsistencies detected. The following patch '
                               'on the patch stack is linked to an upstream '
                               'patch though being markes as false positive:')
                        print('%s => %s' % (origin, fp))
        else:
            for fp_group in self._false_positives:
                if not equivalence_class.is_unrelated(*fp_group):
                    banner('Inconsistencies detected. The following patches '
                           'are marked as related and marked as '
                           'false-positives:')
                    print(fp_group)


class SimRating:
    def __init__(self, msg, diff, diff_lines_ratio):
        """
        :param msg: Message rating
        :param diff: Diff rating
        :param diff_lines_ratio: Ratio of number of lines shorter diff to longer diff
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

    def __eq__(self, other):
        return self.msg == other.msg and self.diff == other.diff and self.diff_lines_ratio == other.diff_lines_ratio

    def __str__(self):
        return '%3.2f message and %3.2f diff, diff lines ratio: %3.2f' % (self.msg, self.diff, self.diff_lines_ratio)


class EvaluationResult(dict):
    """
    An evaluation is a dictionary with a commit hash as key,
    and a list of tuples (hash, SimRating) as value.
    """
    def __init__(self, is_mbox = None, eval_type = None, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.eval_type = eval_type
        self.is_mbox = is_mbox
        self._false_positives = []
        self.fp = None

    def merge(self, other):
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

    @staticmethod
    def from_file(filename, fp_directory=None, fp_must_exist=False):
        log.info('Loading evaluation result')
        with open(filename, 'rb') as f:
            ret = pickle.load(f)
        log.info('  ↪ done')
        ret.fp = FalsePositives(ret.is_mbox, ret.eval_type,
                                fp_directory, fp_must_exist)
        return ret

    def interactive_rating(self, repo, equivalence_class,
                           thresholds, respect_commitdate=False, enable_pager=False):
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

                # Check if those two patches are already related
                if equivalence_class.is_related(orig_commit_hash, cand_commit_hash):
                    already_detected += 1
                    continue

                # Check if patch is already known as false positive
                if self.fp.is_false_positive(equivalence_class, orig_commit_hash, cand_commit_hash):
                    already_false_positive += 1
                    continue

                if sim_rating.diff_lines_ratio < thresholds.diff_lines_ratio:
                    skipped_by_dlr += 1
                    continue

                if respect_commitdate:
                    l = repo[orig_commit_hash]
                    r = repo[cand_commit_hash]
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
                    show_commits(repo, orig_commit_hash, cand_commit_hash, enable_pager)
                    print('Length of list of candidates: %d' % len(candidates))
                    print('Rating: %3.2f (%s)' % (rating, sim_rating))
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
                    if self.eval_type == EvaluationType.Upstream:
                        equivalence_class.tag(cand_commit_hash)

                elif yns == 'n':
                    self.fp.mark(equivalence_class, orig_commit_hash,
                                 cand_commit_hash)

        equivalence_class.optimize()

        print('\n\nSome statistics:')
        print(' Interactive Accepted: %d' % accepted)
        print(' Automatically accepted: %d' % auto_accepted)
        print(' Interactive declined: %d' % declined)
        print(' Automatically declined: %d' % auto_declined)
        print(' Skipped: %d' % skipped)
        print(' Skipped due to previous detection: %d' % already_detected)
        print(' Skipped due to false positive mark: %d' % already_false_positive)
        print(' Skipped by diff length ratio mismatch: %d' % skipped_by_dlr)
        if respect_commitdate:
            print(' Skipped by commit date mismatch: %d' % skipped_by_commit_date)


def best_string_mapping(threshold, left_list, right_list):
    """
    This function tries to find the closest mapping with the best weight of two lists of strings.
    Example:

      List A        List B

    0:  'abc'         'abc'
    1:  'cde'         'cde'
    2:  'fgh'         'fgh
    3:                'fgj

    map_lists will try to map each element of List A to an element of List B, in respect to the given threshold.

    As a[{0,1,2}] == b[{0,1,2}], those values will automatically be mapped. Additionally, a[2] will also be mapped to
    b[3], if the threshold is low enough (cf. 0.5).
    """
    def injective_map(ll, rl, inverse_result=False):
        ret = dict()
        for l_entry in ll:
            for r_entry in rl:
                if l_entry == r_entry:
                    sim = 1
                else:
                    sim = fuzz.token_sort_ratio(l_entry, r_entry) / 100

                if sim < threshold:
                    continue

                if l_entry in ret:
                    _, old_sim = ret[l_entry]
                    if sim < old_sim:
                        continue

                ret[l_entry] = r_entry, sim
        return {(r, l) if inverse_result else (l, r) for l, (r, _) in ret.items()}

    return injective_map(left_list, right_list) | injective_map(right_list, left_list, True)


def rate_diffs(thresholds, l_diff, r_diff):
    filename_compare = best_string_mapping(thresholds.filename, l_diff.patches.keys(), r_diff.patches.keys())
    levenshteins = []
    for l_filename, r_filename in filename_compare:
        l_hunks = l_diff.patches[l_filename]
        r_hunks = r_diff.patches[r_filename]

        levenshtein = []
        hunk_compare = best_string_mapping(thresholds.heading, l_hunks.keys(), r_hunks.keys())

        for l_hunk_heading, r_hunk_heading in hunk_compare:
            lhunk = l_hunks[l_hunk_heading]
            rhunk = r_hunks[r_hunk_heading]

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


def evaluate_commit_pair(repo, thresholds, lhs_commit_hash, rhs_commit_hash):
    # Return identical similarity for equivalent commits
    if lhs_commit_hash == rhs_commit_hash:
        return SimRating(1, 1, 1)

    lhs_commit = repo[lhs_commit_hash]
    rhs_commit = repo[rhs_commit_hash]

    return evaluate_patch_pair(thresholds, (lhs_commit.message, lhs_commit.diff), (rhs_commit.message, rhs_commit.diff))


def _evaluate_commit_pair_helper(thresholds, lhs_commit_hash, rhs_commit_hash):
    return evaluate_commit_pair(_tmp_repo, thresholds, lhs_commit_hash, rhs_commit_hash)


def _evaluation_helper(thresholds, l_r, verbose=False):
    left, right = l_r
    if verbose:
        print('Comparing 1 commit hash against %d commit hashes' % len(right))

    f = functools.partial(_evaluate_commit_pair_helper, thresholds, left)
    results = list(map(f, right))
    results = list(zip(right, results))

    # sort SimRating
    results.sort(key=lambda x: x[1], reverse=True)

    return left, results


def preevaluate_filenames(thresholds, right_files, left_file):
    candidates = []
    for right_file in right_files:
        if thresholds.filename >= 1.0:
            if left_file != right_file:
                continue
        else:
            sim = fuzz.token_sort_ratio(left_file, right_file) / 100
            if sim < thresholds.filename:
                continue
        candidates.append(right_file)
    return left_file, candidates


def preevaluate_commit_list(repo, thresholds, left_hashes, right_hashes, parallelise=True):
    cpu_factor = 0.5

    # Create two dictionaries - one for mails, one for commits that map
    # affected files to commit hashes resp. mailing list Message-IDs
    def file_commit_map(hashes):
        ret = {}
        for hash in hashes:
            files = repo[hash].diff.affected
            for file in files:
                if file not in ret:
                    ret[file] = set()
                ret[file] |= set([hash])
        return ret

    left_files = file_commit_map(left_hashes)
    left_filenames = list(left_files.keys())

    right_files = file_commit_map(right_hashes)
    right_filenames = list(right_files.keys())

    f = functools.partial(preevaluate_filenames, thresholds, right_filenames)

    if parallelise:
        processes = int(cpu_count() * cpu_factor)
        p = Pool(processes=processes, maxtasksperchild=1)
        filename_mapping = p.map(f, left_filenames, chunksize=5)
        p.close()
        p.join()
    else:
        filename_mapping = list(map(f, left_filenames))

    preeval_result = {}
    for left_file, dsts in filename_mapping:
        left_hashes = left_files[left_file]
        right_hashes = set()
        for right_file in dsts:
            right_hashes |= set(right_files[right_file])
        for left_hash in left_hashes:
            left = repo[left_hash]
            for right_hash in right_hashes:
                right = repo[right_hash]
                # don't compare revert patches
                if left.is_revert != right.is_revert:
                    continue
                # skip if we're comparing a patch against itself
                if left_hash == right_hash:
                    continue
                # check if this wasn't already inserted the other way round
                if right_hash in preeval_result and left_hash in preeval_result[right_hash]:
                    continue
                # insert result
                if left_hash not in preeval_result:
                    preeval_result[left_hash] = set()
                preeval_result[left_hash] |= set([right_hash])

    return preeval_result


def evaluate_commit_list(repo, thresholds, is_mbox, eval_type,
                         original_hashes, candidate_hashes,
                         parallelise=False, verbose=False,
                         cpu_factor=1):
    """
    Evaluates two list of original and candidate hashes against each other
    :param repo: repository
    :param thresholds: evaluation thresholds
    :param is_mbox: Is a mailbox involved?
    :param eval_type: evaluation type
    :param original_hashes: list of commit hashes
    :param candidate_hashes: list of commit hashes to compare against
    :param parallelise: Parallelise evaluation
    :param verbose: Verbose output
    :param cpu_factor: number of threads to be spawned is the number of CPUs*cpu_factor
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    processes = int(cpu_count() * cpu_factor)

    log.info('Comparing %d commit hashes against %d commit hashes'
          % (len(original_hashes), len(candidate_hashes)))

    # Bind thresholds to evaluation
    f_eval = functools.partial(_evaluation_helper, thresholds, verbose=verbose)

    if verbose:
        log.info('Running preevaluation.')
    preeval_result = preevaluate_commit_list(repo, thresholds,
                                             original_hashes, candidate_hashes,
                                             parallelise=parallelise)
    if verbose:
        log.info('  ↪ done')

    original_comparisons = len(original_hashes)*len(candidate_hashes)
    preeval_comparisons = sum([len(x) for x in preeval_result.values()])
    log.info('Preevaluation reduced %d comparisons down to %d. (factor: %0.2f)' %
          (original_comparisons, preeval_comparisons,
           original_comparisons / preeval_comparisons))

    global _tmp_repo
    _tmp_repo = repo

    retval = EvaluationResult(is_mbox, eval_type)
    if parallelise:
        p = Pool(processes=processes, maxtasksperchild=1)
        result = p.map(f_eval, preeval_result.items(), chunksize=50)
        p.close()
        p.join()
    else:
        result = list(map(f_eval, preeval_result.items()))

    _tmp_repo = None

    for orig, evaluation in result:
        retval[orig] = evaluation

    return retval
