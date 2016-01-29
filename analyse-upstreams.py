#!/usr/bin/env python3

import functools
from fuzzywuzzy import fuzz
from git import Repo
from multiprocessing import Pool, cpu_count
from subprocess import call
import sys

from PatchStack import \
    KernelVersion, get_commit, cache_commit_hashes, \
    parse_patch_stack_definition, get_commit_hashes
from Tools import TransitiveKeyList, getch, parse_file_to_dictionary, file_to_string, write_dictionary_to_file


REPO_LOCATION = './linux/'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'
SIMILAR_PATCHES_FILE = './similar_patch_list'
FALSE_POSTITIVES_FILES = './false-positives'

SHOW_THRESHOLD = 350
AUTOACCEPT_THRESHOLD = 400


def evaluate_single_patch(original, candidate):
    orig_message, orig_diff, orig_affected, orig_author_date, orig_author_email = get_commit(original)
    cand_message, cand_diff, cand_affected, cand_author_date, cand_author_email = get_commit(candidate)

    rating = 0

    delta = cand_author_date - orig_author_date
    if delta.days < 0:
        return candidate, 0, ''

    # Filtert auch merge commits
    common_changed_files = len(list(set(orig_affected).intersection(cand_affected)))
    if common_changed_files == 0:
        return candidate, 0, ''

    rating += common_changed_files * 20

    o_len = sum(map(len, orig_diff))
    c_len = sum(map(len, cand_diff))
    diff_length_ratio = min(o_len, c_len) / max(o_len, c_len)
    #diff_length_ratio = min(len(orig_diff), len(cand_diff)) / max(len(orig_diff), len(cand_diff))

    if diff_length_ratio < 0.70:
        return candidate, 0, ''

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


def evaluate_patch_list(original_hashes, candidate_hashes, parallelize=False, chunksize=10000):
    """
    Evaluates two list of original and candidate hashes against each other

    :param original_hashes: original patches
    :param candidate_hashes: potential candidates
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    retval = {}

    for i, commit_hash in enumerate(original_hashes):

        sys.stdout.write('\rEvaluating ' + str(i+1) + '/' +
              str(len(original_hashes)) + ' ' + commit_hash)

        f = functools.partial(evaluate_single_patch, commit_hash)
        if parallelize:
            pool = Pool(cpu_count())
            result = pool.map(f, candidate_hashes, chunksize=10000)
            pool.close()
            pool.join()
        else:
            result = map(f, candidate_hashes)

        # filter everything beyond threshold
        result = list(filter(lambda x: x[1] > SHOW_THRESHOLD, result))
        if not result:
            continue

        # sort by ratio
        result.sort(key=lambda x: x[1], reverse=True)

        retval[commit_hash] = result

    sys.stdout.write('\n\n')
    return retval


def merge_evaluation_results(overall_evaluation, evaluation):
    """
    An evaluation is a dictionary with a commit hash as key,
    and a list of 3-tuples (hash, rating, msg) as value.

    Check if this key already exists in the check_list, if yes, then append to the list
    """

    for key, value in evaluation.items():
        if key in overall_evaluation:
            overall_evaluation[key].append(value)
        else:
            overall_evaluation[key] = value


def interactive_rating(transitive_list, false_positive_list, evaluation_result):

    already_false_positive = 0
    already_detected = 0
    accepted = 0
    declined = 0
    skipped = 0

    for orig_commit_hash, candidates in evaluation_result.items():
        for candidate in candidates:
            cand_commit_hash, cand_rating, cand_message = candidate

            if cand_commit_hash == orig_commit_hash:
                print('WHAT THE FUCK IS THE SHIT. go back and check your implementation!')
                getch()

            if orig_commit_hash in false_positive_list and \
               false_positive_list[orig_commit_hash] == cand_commit_hash:
                print('Already marked as false positive. Skipping.')
                already_false_positive += 1
                continue

            if transitive_list.is_related(orig_commit_hash, cand_commit_hash):
                print('Already accepted as similar. Skipping.')
                already_detected += 1
                break # THINK ABOUT THIS!!

            if cand_rating > AUTOACCEPT_THRESHOLD:
                print('Autoaccepting ' + orig_commit_hash + ' <-> ' + cand_commit_hash)
                yns = 'y'
            else:
                yns = ''
                call(['./compare_hashes.sh', orig_commit_hash, cand_commit_hash])
                print('Length of list of candidates: ' + str(len(candidates)))
                print('Rating: ' + str(cand_rating) + ' ' + cand_message)
                print('Yay or nay or skip?')

            while yns not in ['y', 'n', 's']:
                yns = getch()

            if yns == 'y':
                accepted += 1
                transitive_list.insert(orig_commit_hash, cand_commit_hash)
                break # THINK ABOUT THIS!!
            elif yns == 'n':
                declined += 1
                print('nay. Hmkay.')
                false_positive_list[orig_commit_hash] = cand_commit_hash
            else:
                skipped += 1
                print('Skip. Kay...')

    print('\n\nSome statistics:')
    print(' Accepted: ' + str(accepted))
    print(' Declined: ' + str(declined))
    print(' Skipped: ' + str(skipped))
    print(' Skipped due to previous detection: ' + str(already_detected))
    print(' Skipped due to false positive mark: ' + str(already_false_positive))



# Startup
repo = Repo(REPO_LOCATION)

# Load already known positives and false positives
similar_patches = TransitiveKeyList.from_file(SIMILAR_PATCHES_FILE)
false_positives = parse_file_to_dictionary(FALSE_POSTITIVES_FILES, must_exist=False)

# Load patch stack definition
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)


# Check patch against next patch version number, patch by patch
evaluation_result = {}
for index, cur_patch_stack in enumerate(patch_stack_list):

    # Bounds check
    if index == len(patch_stack_list)-1:
        break

    # Skip till version 3.0
    #if cur_patch_stack.patch_version < KernelVersion('3.0'):
    #    continue
    if cur_patch_stack.patch_version > KernelVersion('3.0'):
        break

    next_patch_stack = patch_stack_list[index + 1]

    print('Finding similar patches on: ' +
          str(cur_patch_stack.patch_version) +
          ' <-> ' + str(next_patch_stack.patch_version))

    cache_commit_hashes(cur_patch_stack.commit_hashes)
    cache_commit_hashes(next_patch_stack.commit_hashes)

    this_evaluation = evaluate_patch_list(cur_patch_stack.commit_hashes,
                                          next_patch_stack.commit_hashes,
                                          parallelize=False,
                                          chunksize=50)

    merge_evaluation_results(evaluation_result, this_evaluation)

interactive_rating(similar_patches, false_positives, evaluation_result)

similar_patches.to_file(SIMILAR_PATCHES_FILE)
write_dictionary_to_file(FALSE_POSTITIVES_FILES, false_positives)
