"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import termios
import tty
import shutil
import subprocess
import sys


def get_date_selector(repo, patch_stack_definition, selector):
    # Date selector "Stack Release Date"
    if selector == 'SRD':
        date_selector = lambda x: patch_stack_definition.get_stack_of_commit(x).stack_release_date
    # Date selector "Commit Date"
    elif selector == 'CD':
        date_selector = lambda x: repo[x].commit_date
    else:
        raise NotImplementedError('Unknown date selector: ' % selector)
    return date_selector


def get_commits_from_file(filename, ordered=True, must_exist=True):
    content = file_to_string(filename, must_exist=must_exist)
    if content is None:
        content = ''
    content = content.splitlines()

    # Filter empty lines
    content = filter(None, content)
    # Filter comment lines
    content = filter(lambda x: not x.startswith('#'), content)
    # return filtered list or set
    if ordered:
        return list(content)
    else:
        return set(content)


def file_to_string(filename, must_exist=True):
    try:
        # I HATE ENCONDING!
        # Anyway, opening a file as binary and decoding it to iso8859 solves the problem :-)
        with open(filename, 'rb') as f:
            retval = str(f.read().decode('iso8859'))
            f.close()
    except FileNotFoundError:
        print('Warning, file ' + filename + ' not found!')
        if must_exist:
            raise
        return None

    return retval


def format_date_ymd(dt):
    return dt.strftime('%Y-%m-%d')


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def _ansi_clrscr():
    sys.stdout.write('\x1b[2J\x1b[H')


def _fix_encoding(string):
    return string.encode('utf-8').decode('ascii', 'ignore')


def _format_message(commit):
    message = ['Commit:     %s' % commit.commit_hash,
               'Author:     %s <%s>' % (_fix_encoding(commit.author), commit.author_email),
               'AuthorDate: %s' % commit.author_date,
               'Committer   %s <%s>' % (_fix_encoding(commit.committer), commit.committer_email),
               'CommitDate: %s' % commit.commit_date,
               'Note: %s' % commit.note,
               ''] + _fix_encoding(commit.raw_message).split('\n')
    return message


def pager(text, enable_pager=True):
    _, lines = shutil.get_terminal_size()
    if text.count('\n') > lines and enable_pager:
        p = subprocess.Popen(['less', '-eFX'], stdin=subprocess.PIPE)
        p.stdin.write(bytes(text, 'utf-8'))
        p.stdin.close()
        p.wait()
    else:
        _ansi_clrscr()
        print(text)


def show_commit(repo, hash):
    commit = repo[hash]
    message = _format_message(commit) + commit.raw_diff.split('\n')
    _ansi_clrscr()
    print('\n'.join(message))


def show_commits(repo, left_hash, right_hash):
    def side_by_side(left, right, split_length):
        ret = []
        while len(left) or len(right):
            line = ''
            if len(left):
                line = _fix_encoding(left.pop(0)).expandtabs(6)[0:split_length]
            line = line.ljust(split_length)
            line += ' | '
            if len(right):
                line += _fix_encoding(right.pop(0)).expandtabs(6)[0:split_length]
            ret.append(line)
        return ret

    left_commit = repo[left_hash]
    right_commit = repo[right_hash]

    left_message = _format_message(left_commit)
    right_message = _format_message(right_commit)

    left_diff = left_commit.raw_diff.split('\n')
    right_diff = right_commit.raw_diff.split('\n')

    columns, _ = shutil.get_terminal_size()
    maxlen = int((columns-3)/2)

    split_length = max(map(len, left_diff + left_message))
    if split_length > maxlen:
        split_length = maxlen

    text = []
    text += side_by_side(left_message, right_message, split_length)
    text += ['-' * (split_length+1) + '+' + '-' * (columns-split_length-2)]
    text += side_by_side(left_diff, right_diff, split_length)
    _ansi_clrscr()
    print('\n'.join(text))
