#!/usr/bin/env python3

from datetime import datetime
import functools
from fuzzywuzzy import fuzz
from git import Repo
from multiprocessing import Pool, Lock, Value, cpu_count
import os
from subprocess import call
import time

from PatchStack import PatchStack, KernelVersion, VersionPoint, parse_patch_stack_definition, get_commit_hashes


REPO_LOCATION = './linux/'
DIFFS_LOCATION = './log/diffs/'
AFFECTED_FILES_LOCATION = './log/affected_files/'
MESSAGES_LOCATION = './log/messages/'
AUTHOR_DATE_LOCATION = './log/author_dates/'
AUTHOR_EMAIL_LOCATION = './log/author_emails/'
CORRELATION_LIST = './similar_patch_list'

RESULTS = './upstream-results/'
THRESHOLD = 200

def getch():
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
        finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def file_to_string(filename):
    with open(filename, 'rb') as f:
        retval = str(f.read().decode('iso8859')) # looks strange, but this is a must due to encoding difficulties
        f.close()
    return retval


def evaluate(original, candidate):
    orig_message, orig_diff, orig_affected, orig_author_date, orig_author_email = candidates[original]
    cand_message, cand_diff, cand_affected, cand_author_date, cand_author_email = candidates[candidate]

    rating = 0

    delta = cand_author_date - orig_author_date
    if delta.days < 0:
        return candidate, 0, ''

    # Filtert auch merge commits
    common_changed_files = len(list(set(orig_affected).intersection(cand_affected)))
    if common_changed_files == 0:
        return candidate, 0, ''

    rating += common_changed_files * 20

    diff_length_ratio = min(len(orig_diff), len(cand_diff)) / max(len(orig_diff), len(cand_diff))
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

print('Caching candidate commits... This may take a while...')
candidates = {}
for i in cand_commit_hashes + p.commit_hashes:
    message = file_to_string(MESSAGES_LOCATION + i)
    diff = file_to_string(DIFFS_LOCATION + i)
    diff = diff.split('\n')
    affected = file_to_string(AFFECTED_FILES_LOCATION + i)
    affected = list(filter(None, affected.split('\n')))
    affected.sort()
    author_date = file_to_string(AUTHOR_DATE_LOCATION + i)
    author_date = datetime.fromtimestamp(int(author_date))
    author_email = file_to_string(AUTHOR_EMAIL_LOCATION + i)
    candidates[i] = (message, diff, affected, author_date, author_email)
print('done')

correlation_file = file_to_string(CORRELATION_LIST)
correlation_list = {}
if len(correlation_file):
    correlation_file = list(filter(None, correlation_file.split('\n')))
    for i in correlation_file:
        orig, partner = i.split(' ')
        correlation_list[orig] = partner

manual_check_list = {}

for i, commit_hash in enumerate(p.commit_hashes):
    if commit_hash in correlation_list:
        print('Skipping ' + commit_hash + ': Already evaluated.')
        continue

    print('Evaluating ' + str(i+1) + '/' + str(len(p.commit_hashes)) + ' ' + commit_hash)

    pool = Pool(cpu_count()+2)
    f = functools.partial(evaluate, commit_hash)
    result = pool.map(f, cand_commit_hashes)

    pool.close()
    pool.join()

    # filter everything beyond threshold
    result = list(filter(lambda x: x[1] > THRESHOLD, result))
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
        call(['./compare_hashes.sh', orig, commit_hash])
        print('Rating: ' + str(rating) + ' ' + message)
        yn  = ''
        print('Yay or nay? ')
        while not yn in ['y', 'n']:
                yn = getch()
        if yn == 'y':
                correlation_list[orig] = commit_hash
                break
        else:
                print('nay')

with open(CORRELATION_LIST, 'w') as f:
        for orig, partner in correlation_list.items():
                f.write(orig + ' ' + partner + '\n')
        f.close()
