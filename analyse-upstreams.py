#!/usr/bin/env python3

import functools
from fuzzywuzzy import fuzz
from git import Repo
from multiprocessing import Pool, cpu_count
from subprocess import call
import sys

from PatchStack import \
    KernelVersion, get_commit, cache_commit_hashes, \
    parse_patch_stack_definition, get_commit_hashes, TransitiveKeyList, transitive_key_list_from_file
from Tools import getch, parse_file_to_dictionary, file_to_string, write_dictionary_to_file


REPO_LOCATION = './linux/'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'
SIMILAR_PATCHES_FILE = './similar_patch_list'

RESULTS = './upstream-results/'
SHOW_THRESHOLD = 250
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


def evaluate_patch_list(original_hashes, candidate_hashes):
    """
    Evaluates two list of original and candidate hashes against each other

    :param original_hashes: original patches
    :param candidate_hashes: potential candidates
    :return: a dictionary with originals as keys and a list of potential candidates as value
    """

    retval = {}

    for i, commit_hash in enumerate(original_hashes):
        if commit_hash in similar_patches:
            continue

        sys.stdout.write('\rEvaluating ' + str(i+1) + '/' +
              str(len(original_hashes)) + ' ' + commit_hash)


        f = functools.partial(evaluate_single_patch, commit_hash)
        #pool = Pool(cpu_count())
        #result = pool.map(f, candidate_hashes, chunksize=30)
        #pool.close()
        #pool.join()
        result = map(f, candidate_hashes)

        # filter everything beyond threshold
        result = list(filter(lambda x: x[1] > SHOW_THRESHOLD, result))
        if not result:
            continue

        # sort by ratio
        result.sort(key=lambda x: x[1], reverse=True)

        retval[commit_hash] = result

        with open(RESULTS + commit_hash, 'w') as f:
            for candidate, rating, message in result:
                f.write(candidate + ' ' +
                        str(rating) + ' ' +
                        message + '\n')
            f.close()
    sys.stdout.write('\n\n')
    return retval


repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

similar_patches = {}
check_list = {}

similar_patches_file = file_to_string(SIMILAR_PATCHES_FILE, must_exist=False)
if similar_patches_file is not None and len(similar_patches_file):
    similar_patches_file = list(filter(None, similar_patches_file.split('\n')))
    for i in similar_patches_file:
        orig_commit_hash, partner = i.split(' ')
        similar_patches[orig_commit_hash] = partner


# Check patch stacks against each other
for index, cur_patch_stack in enumerate(patch_stack_list):
    # Bounds check
    if index == len(patch_stack_list)-1:
        break

    # Skip till version 3.0
    #if cur_patch_stack.patch_version < KernelVersion('3.18'):
    #    continue
    #if cur_patch_stack.patch_version > KernelVersion('3.20'):
    #    break
    break

    next_patch_stack = patch_stack_list[index + 1]

    print('Finding similar patches on: ' +
          str(cur_patch_stack.patch_version) +
          ' <-> ' + str(next_patch_stack.patch_version))

    cache_commit_hashes(cur_patch_stack.commit_hashes)
    cache_commit_hashes(next_patch_stack.commit_hashes)

    evaluation = {}
    evaluation = evaluate_patch_list(cur_patch_stack.commit_hashes, next_patch_stack.commit_hashes)
    # Only available in python > 3.5
    #check_list = {**check_list, **evaluation}
    check_list.update(evaluation)


# Manual rating
for orig_commit_hash, candidates in check_list.items():
    for candidate in candidates:
        cand_commit_hash, cand_rating, cand_message = candidate

        if cand_rating > AUTOACCEPT_THRESHOLD:
            print('Autoaccepting ' + orig_commit_hash + ' <-> ' + cand_commit_hash)
            yn = 'y'
        else:
            yn = ''
            call(['./compare_hashes.sh', orig_commit_hash, cand_commit_hash])
            print('Rating: ' + str(cand_rating) + ' ' + cand_message)
            print('Yay or nay? ')

        while yn not in ['y', 'n']:
                yn = getch()

        if yn == 'y':
                similar_patches[orig_commit_hash] = cand_commit_hash
                break
        else:
                print('nay. Hmkay.')

with open(SIMILAR_PATCHES_FILE, 'w') as f:
        for orig_commit_hash, partner in similar_patches.items():
                f.write(orig_commit_hash + ' ' + partner + '\n')
        f.close()
