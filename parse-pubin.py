#!/usr/bin/env python
""" tools/scripts/import-public-inbox <checked-out-git> <args to parsearchive> """

import sys
import subprocess

gitdir = sys.argv[1]
lower_bound = int(sys.argv[2])
upper_bound = int(sys.argv[3])
parsemail_args = sys.argv[4:]

print("Getting list of patches...")
subprocess.call(['git', '-C', gitdir, 'checkout', 'master'], stdout=subprocess.DEVNULL)
commits = subprocess.check_output(['git', '-C', gitdir, 'log', '--reverse', '--oneline'], encoding='UTF-8').splitlines()

print("getting header lines for mbox format")
froms = subprocess.check_output(['git', '-C', gitdir, 'log', '--reverse', '--pretty=format:From %ae %ad'], encoding='UTF-8').splitlines()
print(f"Importing mails {lower_bound} to {upper_bound}..")
num_commits = len(commits)
messages = []
for (i, message_info) in enumerate(zip(froms, commits)):
    if i < lower_bound:
        continue
    if i > upper_bound:
        break
    fromline, commit = message_info
    # if i % (num_commits // 1000) == 0:
    #     print((i * 100) / num_commits, "% imported")

    sha = commit.split(' ')[0]
    messages += [fromline + '\n' + subprocess.check_output(['git', '-C', gitdir, 'show', sha+':m'], encoding='UTF-8', errors='replace')]
    # if i % 10000 == 0 and i != 0:
    #     with open('publicinboxtmp', 'wb') as f:
    #         f.write('\n'.join(messages).encode('utf-8'))
        # subprocess.call(['python3', 'manage.py', 'parsearchive'] + parsemail_args + ['publicinboxtmp'])
with open('publicinboxtmp', 'wb') as f:
    f.write('\n'.join(messages).encode('utf-8'))
subprocess.call(['python3', 'manage.py', 'parsearchive'] + parsemail_args + ['publicinboxtmp'])
