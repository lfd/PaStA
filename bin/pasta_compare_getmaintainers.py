import argparse
import random
import re
import shutil
import subprocess
import tempfile
import base64

from collections import defaultdict
from logging import getLogger
from os.path import join
from os import chdir, mkdir
from pathlib import Path

from pypasta import LinuxMailCharacteristics
from pypasta.LinuxMaintainers import load_maintainers, Section

log = getLogger(__name__[-15:])

linux_directory_skeleton = {'arch',
                          'drivers',
                          'fs',
                          'include',
                          'init',
                          'ipc',
                          'kernel',
                          'lib',
                          'scripts',
                          'Documentation',
                            }

linux_file_skeleton = {'COPYING',
                       'CREDITS',
                       'Kbuild',
                       'Makefile',
                       'README'}

def isBase64(s):
    return b'Content-Transfer-Encoding: base64' in s

def repo_get_and_write_file(repo, ref, filename, destination):
    content = repo.get_blob(ref, filename)
    with open(join(destination, filename), 'wb') as f:
        f.write(content)


def compare_getmaintainers(config, argv):
    parser = argparse.ArgumentParser(prog='compare_getmaintainers',
                                     description='compare PaStA and official get_maintainer')
    parser.add_argument('--m_id', metavar='m_id', type=str, nargs='+', help='Which message_id\'s to use\n'
                                                                            'Important: see to it that the mailboxes'
                                                                            ' affected by the provided id\'s are '
                                                                            'active in the current Config')
    parser.add_argument('--bulk', metavar='bulk', type=int, help='Bulk-Mode: If no message_id is provided, how many '
                                                          'message_id\'s should be picked randomly and processed')

    args = parser.parse_args(argv)

    victims = args.m_id
    bulk = args.bulk

    linusTorvaldsTuple = (
        'torvalds@linux-foundation.org', str(Section.Status.Buried))

    repo = config.repo
    repo.register_mbox(config)

    all_message_ids = None

    if victims is None:
        all_message_ids = list(repo.mbox.get_ids(
            time_window=(config.mbox_mindate, config.mbox_maxdate),
            allow_invalid=False))
        all_message_ids = [x for x in all_message_ids if
                           LinuxMailCharacteristics._patches_linux(repo[x]) and 
                           LinuxMailCharacteristics._process_mail(x, repo)]
        if bulk is None:
            victims = [random.choice(all_message_ids)]
        else:
            victims = random.sample(all_message_ids, bulk)

    tmp = defaultdict(list)
    for victim in victims:
        version = repo.linux_patch_get_version(repo[victim])
        tmp[version].append(victim)
    victims = tmp

    maintainers_version = load_maintainers(config, victims.keys())

    d_tmp = tempfile.mkdtemp()
    try:
        for dir in linux_directory_skeleton:
            mkdir(join(d_tmp, dir))

        for file in linux_file_skeleton:
            Path(join(d_tmp, file)).touch()

        accepted = 0
        declined = 0
        skipped = 0
        for version, message_ids in victims.items():
            # build the structure anew for every different version
            repo_get_and_write_file(repo, version, 'MAINTAINERS', d_tmp)
            repo_get_and_write_file(repo, version, 'scripts/get_maintainer.pl', d_tmp)
            linux_maintainers = maintainers_version[version]

            for message_id in message_ids:
                log.info('Processing %s (%s)' % (message_id, version))

                message_raw = repo.mbox.get_raws(message_id)[0]

                if isBase64(message_raw):
                    log.error('Detected base64 encoded mail, skipping it silently')
                    continue

                f_message = join(d_tmp, 'm')
                with open(f_message, 'wb') as f:
                    f.write(message_raw)

                chdir(d_tmp)

                pl = subprocess.Popen(
                    ['perl ' + join(d_tmp, join('scripts', 'get_maintainer.pl')) + ' '
                     + f_message
                     + ' --subsystem --status --separator \; --nogit --nogit-fallback --roles --norolestats '
                       '--no-remove-duplicates --no-keywords']
                    , shell=True, stdout=subprocess.PIPE, stderr = subprocess.PIPE)

                pl_output = pl.communicate()[0].decode('utf-8')

                pl_err = pl.communicate()[1].decode('utf-8')

                if 'no longer supported in regex' in pl_err:
                    log.error('silently skipping a regex error')
                    continue

                if pl.returncode != 0 or pl_output == '\n\n':
                    log.error('Unknown error while executing perl script, skipping')
                    skipped += 1
                    continue

                patch = repo[message_id]
                subsystems = linux_maintainers.get_sections_by_files(patch.diff.affected)

                pasta_people = set()
                pasta_lists = set()
                for subsystem in subsystems:
                    lists, maintainers, reviewers = linux_maintainers.get_maintainers(subsystem)
                    subsystem_obj = linux_maintainers[subsystem]
                    subsystem_states = subsystem_obj.status

                    pasta_lists |= lists

                    for reviewer in reviewers:
                        pasta_people.add((reviewer[1].lower(), 'reviewer'))#, subsystem[0:40]))

                    for maintainer in maintainers:
                        if len(subsystem_states) != 1:
                            log.error(
                                'maintainer for subsystem %s had more than one status or none? '
                                'Lookup message_id %s' % (subsystem, message_id))
                        elif subsystem_states[0] is Section.Status.Maintained:
                            status = 'maintainer'
                        elif subsystem_states[0] is Section.Status.Supported:
                            status = 'supporter'
                        elif subsystem_states[0] is Section.Status.OddFixes:
                            status = 'odd fixer'
                        else:
                            status = str(subsystem_states[0])

                        to_be_appended = (maintainer[1].lower(), status)#, subsystem[0:40])

                        if to_be_appended != linusTorvaldsTuple and to_be_appended[0] is not '':
                            pasta_people.add(to_be_appended)

                log.info('maintainers successfully retrieved by PaStA')

                pl_split = pl_output.split('\n')
                pl_people = pl_split[0].split(';')
                pl_subsystems = set(pl_split[2].split(';'))

                # pl_people will contain lists. Filter them.
                pl_lists = {list.split(' ')[0] for list in pl_people if ' list' in list}
                pl_people = {person for person in pl_people if ' list' not in person}

                # First, check if subsystems actually match. Unfortunatelly,
                # get_maintainers crops subsystem names. Hence, only compare
                # 40 characters of the name
                pasta_subsystems_abbrev = {subsystem[0:40] for subsystem in subsystems}
                pl_subsystems_abbrev = {subsystem[0:40] for subsystem in pl_subsystems}

                isAccepted = True

                missing_subsys_pasta = pl_subsystems_abbrev - pasta_subsystems_abbrev
                missing_subsys_pl = pasta_subsystems_abbrev - pl_subsystems_abbrev
                if len(missing_subsys_pasta):
                    isAccepted = False
                    log.warning('Subsystems: Missing in PaStA: %s' % missing_subsys_pasta)
                if len(missing_subsys_pl):
                    isAccepted = False
                    log.warning('Subsystems: Missing in get_maintainers: %s' % missing_subsys_pl)
                if pasta_subsystems_abbrev == pl_subsystems_abbrev:
                    log.info('Subsystems: Match')

                # Second, check if list entries match
                missing_lists_pasta = pl_lists - pasta_lists
                missing_lists_pl = pasta_lists - pasta_lists
                if len(missing_lists_pasta):
                    isAccepted = False
                    log.warning('Lists: Missing in PaStA: %s' % missing_lists_pasta)
                if len(missing_lists_pl):
                    isAccepted = False
                    log.warning('Lists: Missing in get_maintainers: %s' % missing_lists_pl)
                if pl_lists == pasta_lists:
                    log.info('Lists: Match')

                # Third, check if maintainers / reviewers / supports match. We now don't care
                # about the subsystem any longer, but we do care about the state of the person
                pl_person_regex = re.compile('.*<(.*)> \(([^:]*)(?::(.*))?\)')
                pl_system_regex = re.compile('(.*) \((.*):(.*)\)')
                match = True
                for pl_person in pl_people:
                    match = pl_person_regex.match(pl_person)
                    if not match:
                        # raise ValueError('regex did not match for person %s from message_id %s'
                        #                 % (pl_person, message_id))
                        match = pl_system_regex.match(pl_person)
                        if not match:
                            raise ValueError('regex did not match for person %s from message_id %s'
                                             % (pl_person, message_id))

                    triple = match.group(1).lower(), match.group(2).lower() #, match.group(3)[0:40]

                    if triple in pasta_people:
                        pasta_people.remove(triple)
                    else:
                        isAccepted = False
                        log.warning('People: Missing entry for %s (%s)' % triple)
                        match = False

                if len(pasta_people):
                    isAccepted = False
                    log.warning('People: Too much entries in PaStA: %s' % pasta_people)
                    match = False

                if match:
                    log.info('People: Match')
                if isAccepted:
                    accepted += 1
                else:
                    declined += 1
                    with open('../my_wrong_file.txt', 'a') as f:
                        f.write('\'' + message_id + '\' ')

        total = accepted + declined + skipped
        log.info('\nFrom a total of %s message_id\'s:\n%u passed comparison\n%u failed comparison\n%u skipped'
                 % (total, accepted, declined, skipped))
        if total > 0:
            log.info('Acceptance/Reject/Skipped rate: %s / %s / %s'
                    % ((accepted/total)*100, (declined/total)*100, (skipped/total)*100))
        else:
            log.info('No messages tested')

    finally:
        shutil.rmtree(d_tmp)
