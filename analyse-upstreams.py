#!/usr/bin/env python3

import functools
from fuzzywuzzy import fuzz
from git import Repo
from multiprocessing import Pool, cpu_count
from subprocess import call

from PatchStack import PatchStack, \
    VersionPoint, get_commit_hashes, get_commit, \
    cache_commit_hashes, file_to_string
from Tools import getch


REPO_LOCATION = './linux/'
CORRELATION_LIST = './similar_patch_list'

RESULTS = './upstream-results/'
SHOW_THRESHOLD = 200
AUTOACCEPT_THRESHOLD = 400


def evaluate(original, candidate):
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


repo = Repo(REPO_LOCATION)
base = VersionPoint('v3.0', '3.0', '2011-07-22')
patch = VersionPoint('analysis-3.0-rt1', '3.0-rt1', '2011-07-22')
p = PatchStack(repo, base, patch)

# Load list of potential candidate commit hashes
print('Loading list of candidate commit hashes')
cand_commit_hashes = get_commit_hashes(repo, 'v3.0', 'v3.2')
print('done')

cache_commit_hashes(cand_commit_hashes + p.commit_hashes)

similar_patches_file = file_to_string(CORRELATION_LIST, must_exist=False)
similar_patches = {}
if similar_patches_file is not None and len(similar_patches_file):
    similar_patches_file = list(filter(None, similar_patches_file.split('\n')))
    for i in similar_patches_file:
        orig, partner = i.split(' ')
        similar_patches[orig] = partner

manual_check_list = {}

for i, commit_hash in enumerate(p.commit_hashes):
    if commit_hash in similar_patches:
        print('Skipping ' + commit_hash + ': Already evaluated.')
        continue

    print('Evaluating ' + str(i+1) + '/' + str(len(p.commit_hashes)) + ' ' + commit_hash)

    pool = Pool(cpu_count()+2)
    f = functools.partial(evaluate, commit_hash)
    result = pool.map(f, cand_commit_hashes)

    pool.close()
    pool.join()

    # filter everything beyond threshold
    result = list(filter(lambda x: x[1] > SHOW_THRESHOLD, result))
    if not result:
        continue

    # sort by ratio
    result.sort(key=lambda x: x[1], reverse=True)

    manual_check_list[commit_hash] = result

    with open(RESULTS + commit_hash, 'w') as f:
        for candidate, rating, message in result:
            f.write(candidate + ' ' +
                    str(rating) + ' ' +
                    message + '\n')
        f.close()


for orig, candidates in manual_check_list.items():
    for cand in candidates:
        commit_hash, rating, message = cand

        if rating > AUTOACCEPT_THRESHOLD:
            yn = 'y'
        else:
            yn = ''
            call(['./compare_hashes.sh', orig, commit_hash])
            print('Rating: ' + str(rating) + ' ' + message)
            print('Yay or nay? ')

        while yn not in ['y', 'n']:
                yn = getch()

        if yn == 'y':
                similar_patches[orig] = commit_hash
                break
        else:
                print('nay. Hmkay.')

with open(CORRELATION_LIST, 'w') as f:
        for orig, partner in similar_patches.items():
                f.write(orig + ' ' + partner + '\n')
        f.close()
