import functools

import sys
from fuzzywuzzy import fuzz
from math import ceil
from multiprocessing import Pool, cpu_count
from subprocess import call

from PatchStack import get_commit
from Tools import getch

def preevaluate_single_patch(original, candidate):
    orig_message, orig_diff, orig_affected, orig_author_date, orig_author_email = get_commit(original)
    cand_message, cand_diff, cand_affected, cand_author_date, cand_author_email = get_commit(candidate)

    if original == candidate:
        return False

    delta = cand_author_date - orig_author_date
    if delta.days < 0:
        return False

    if 'serial: 8250: Call flush_to_ldisc when the irq is threaded' in orig_message and \
        'serial: 8250: Clean up the locking for -rt' in cand_message:
        return False

    if 'serial: 8250: Call flush_to_ldisc when the irq is threaded' in cand_message and \
        'serial: 8250: Clean up the locking for -rt' in orig_message:
        return False

    # Filtert auch merge commits
    common_changed_files = len(list(set(orig_affected).intersection(cand_affected)))
    if common_changed_files == 0:
        return False

    return True


def evaluate_single_patch(original, candidate):

    orig_message, orig_diff, orig_affected, orig_author_date, orig_author_email = get_commit(original)
    cand_message, cand_diff, cand_affected, cand_author_date, cand_author_email = get_commit(candidate)

    rating = 0
    delta = cand_author_date - orig_author_date

    # Filtert auch merge commits
    common_changed_files = len(list(set(orig_affected).intersection(cand_affected)))

    rating += common_changed_files * 20

    #o_len = sum(map(len, orig_diff))
    #c_len = sum(map(len, cand_diff))
    #diff_length_ratio = min(o_len, c_len) / max(o_len, c_len)
    diff_length_ratio = min(len(orig_diff), len(cand_diff)) / max(len(orig_diff), len(cand_diff))

    if diff_length_ratio < 0.70:
        return None

    if diff_length_ratio > 0.999:
        rating += 80
    else:
        rating += int(diff_length_ratio*100 - 70)

    # compare author date
    # killer argument, this means that orig and
    # cand have the _exact_ same timestamp

    if orig_author_date == cand_author_date:
        rating += 150
    elif delta.days < 100:
        rating += 100 - delta.days
    else:
        rating -= delta.days - 100

    if orig_author_email == cand_author_email:
        rating += 50
    else:
        rating -= 20

    rating += fuzz.token_sort_ratio(orig_diff, cand_diff)

    rating += fuzz.token_sort_ratio(orig_message, cand_message)

    message = 'diff-length-ratio: ' + str(diff_length_ratio)

    return candidate, rating, message


def evaluate_patch_list(original_hashes, candidate_hashes,
                        parallelize=False, verbose=False):
    """
    Evaluates two list of original and candidate hashes against each other

    :param original_hashes: original patches
    :param candidate_hashes: potential candidates
    :param parallelize: Parallelize evaluation
    :param chunksize: chunksize
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    retval = {}
    num_cpus = int(cpu_count() * 1.25)

    print('Evaluating ' + str(len(original_hashes)) + ' commit hashes against ' +
          str(len(candidate_hashes)) + ' commit hashes')

    for i, commit_hash in enumerate(original_hashes):

        f = functools.partial(preevaluate_single_patch, commit_hash)
        this_candidate_hashes = list(filter(f, candidate_hashes))

        if verbose:
            sys.stdout.write('\r Evaluating ' + str(i) + '/' + str(len(original_hashes)))

        f = functools.partial(evaluate_single_patch, commit_hash)
        if parallelize and len(this_candidate_hashes) > 5*num_cpus:
            chunksize = ceil(len(this_candidate_hashes) / num_cpus)
            pool = Pool(num_cpus)
            result = pool.map(f, this_candidate_hashes, chunksize=chunksize)
            pool.close()
            pool.join()
        else:
            result = list(map(f, this_candidate_hashes))

        if not result:
            continue

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
                call(['./compare_hashes.sh', orig_commit_hash, cand_commit_hash])
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