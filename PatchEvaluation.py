import sys
import functools
from fuzzywuzzy import fuzz
from math import ceil
from multiprocessing import Pool, cpu_count

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
    common_changed_files = len(list(set(orig.affected).intersection(cand.affected)))
    if common_changed_files == 0:
        return False

    return True


def evaluate_single_patch(original_hash, candidate_hash):

    orig = get_commit(original_hash)
    cand = get_commit(candidate_hash)

    # Filtert auch merge commits
    #common_changed_files = len(list(set(orig_affected).intersection(cand_affected)))
    #rating += common_changed_files * 20

    o_len = sum(map(len, orig.diff))
    c_len = sum(map(len, cand.diff))
    diff_length_ratio = min(o_len, c_len) / max(o_len, c_len)
    #diff_length_ratio = min(len(orig_diff), len(cand_diff)) / max(len(orig_diff), len(cand_diff))

    if diff_length_ratio < 0.75:
        return None

    # killer argument, this means that orig and
    # cand have the _exact_ same timestamp
    if orig.author_date == cand.author_date:
        return candidate_hash, 1.0, 'Exact same date'

    # compare author date
    #delta = cand_author_date - orig_author_date
    #if delta.days < 100:
    #    rating += 100 - delta.days

    if orig.author_email == cand.author_email:
        email_rating = 0.0
    else:
        email_rating = 0



    msg_rating = 0.4 * (fuzz.token_sort_ratio(orig.message, cand.message)/100)
    diff_rating = 0.8 * (fuzz.token_sort_ratio(orig.diff, cand.diff)/100)

    rating = email_rating + msg_rating + diff_rating

    message = str('Email: ' + str(email_rating) +
                  ' Msg: ' + str(msg_rating) +
                  ' Diff: ' + str(diff_rating))

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
