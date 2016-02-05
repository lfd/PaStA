import functools
from fuzzywuzzy import fuzz
from math import ceil
from multiprocessing import Pool, cpu_count
from statistics import mean
import sys

from PatchStack import get_commit
from Tools import getch, compare_hashes


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
    if diff_length_ratio < 0.5:
        return candidate_hash, 0, 'Diff Length Ratio mismatch: ' + str(diff_length_ratio)

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
                        message += 'LEVENRATE: ' + str(rating) + ' || '

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

    # Rate msg and diff by 0.4/0.8
    rating = 0.4 * msg_rating + 0.8 * diff_rating

    # Generate evaluation summary message
    message = str(' Msg: ' + str(msg_rating*100) +
                  '% Diff: ' + str(diff_rating*100) +
                  '% || DLR' + str(diff_length_ratio))

    return candidate_hash, rating, message


def _preevaluation_helper(candidate_hashes, orig_hash):
    f = functools.partial(preevaluate_single_patch, orig_hash)
    return orig_hash, list(filter(f, candidate_hashes))


def evaluate_patch_list(original_hashes, candidate_hashes,
                        parallelize=False, verbose=False):
    """
    Evaluates two list of original and candidate hashes against each other

    :param original_hashes: original patches
    :param candidate_hashes: potential candidates
    :param parallelize: Parallelize evaluation
    :param verbose: Verbose output
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    retval = {}
    num_cpus = int(cpu_count() * 1.25)

    print('Evaluating ' + str(len(original_hashes)) + ' commit hashes against ' +
          str(len(candidate_hashes)) + ' commit hashes')

    if verbose:
        print('Running preevaluation.')
    f = functools.partial(_preevaluation_helper, candidate_hashes)
    if parallelize:
        p = Pool(num_cpus)
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
            sys.stdout.write('\r Evaluating ' + str(i) + '/' +
                             str(len(original_hashes)))

        # Do we have to consider the commit_hash?
        if commit_hash not in preeval_result:
            continue

        this_candidate_hashes = preeval_result[commit_hash]
        f = functools.partial(evaluate_single_patch, commit_hash)

        if parallelize and len(this_candidate_hashes) > 5*num_cpus:
            chunksize = ceil(len(this_candidate_hashes) / num_cpus)
            pool = Pool(num_cpus)
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


def merge_evaluation_results(overall_evaluation, evaluation):
    """
    An evaluation is a dictionary with a commit hash as key,
    and a list of 3-tuples (hash, rating, msg) as value.

    Check if this key already exists in the check_list, if yes, then append to the list
    """

    for key, value in evaluation.items():
        # Skip empty evaluation lists
        if not value:
            continue

        if key in overall_evaluation:
            overall_evaluation[key].append(value)
        else:
            overall_evaluation[key] = value

        overall_evaluation[key].sort(key=lambda x: x[1], reverse=True)


def interactive_rating(transitive_list, false_positive_list, evaluation_result,
                       autoaccept_threshold, interactive_threshold):

    already_false_positive = 0
    already_detected = 0
    auto_accepted = 0
    auto_declined = 0
    accepted = 0
    declined = 0
    skipped = 0

    for orig_commit_hash, candidates in evaluation_result.items():
        for candidate in candidates:
            cand_commit_hash, cand_rating, cand_message = candidate

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

            # Maybe we can autoaccept the patch?
            if cand_rating > autoaccept_threshold:
                auto_accepted += 1
                yns = 'y'
            # or even automatically drop it away?
            elif cand_rating < interactive_threshold:
                auto_declined += 1
                continue
            # Nope? Then let's do an interactive rating by a human
            else:
                yns = ''
                compare_hashes(orig_commit_hash, cand_commit_hash)
                print('Length of list of candidates: ' + str(len(candidates)))
                print('Rating: ' + str(cand_rating) + ' ' + cand_message)
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
