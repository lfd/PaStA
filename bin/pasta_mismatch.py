import os
import sys

from pygit2 import init_repository
from datetime import datetime
from logging import getLogger
from multiprocessing import Pool, cpu_count
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

import git as gitpython

log = getLogger(__name__[-15:])

_config = None
_tmp_repo = None
bare = False
repo = init_repository('name', bare)

def detectMismatch(self, repo, commit_hash, filename):
    commit = repo[commit_hash]
    author = Commit.get_signature(commit.author)
    committer = Commit.get_signature(commit.committer)
    signatureName = Signature.name()
    signatureEmail = Signature.email()
    signatureTime = Signature.time()
    signatureOffset = Signature.offset()
    bashCommand = './scripts/get_maintainer.pl' + filename
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    getMaintainer, error = process.communicate()

    if (committer != getMaintainer):
        return "Mismtatch"

def printMistmatches():
    fileObj = file1.open("git_trees_list.txt")
    [git_trees] = file1.read()
    for obj in git_trees:
        print getCommitInfo(obj, filename)
