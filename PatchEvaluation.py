import functools
from fuzzywuzzy import fuzz
from math import ceil
from multiprocessing import Pool, cpu_count
from statistics import mean
import sys

from PatchStack import get_commit
from Tools import EvaluationResult


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
            sys.stdout.write('\r Evaluating %d/%d' % (i, len(original_hashes)))

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

        # Check if there are no results at all
        if not result:
            continue

        # sort by ratio
        result.sort(key=lambda x: x[1], reverse=True)

        retval[commit_hash] = result

    if verbose:
        sys.stdout.write('\n')

    return retval
