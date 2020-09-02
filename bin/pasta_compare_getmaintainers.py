import argparse
import random
import re
import shutil
import subprocess
import tempfile

from collections import defaultdict
from os.path import join
from os import chdir, mkdir
from pathlib import Path

from pypasta.LinuxMaintainers import load_maintainers, Section
from pypasta.Linux import *

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
                            'Documentation'}

linux_file_skeleton = {'COPYING',
                       'CREDITS',
                       'Kbuild',
                       'Makefile',
                       'README'}

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

    repo = config.repo
    _, clustering = config.load_cluster()

    if victims:
        tmp = defaultdict(set)
        for victim in victims:
            version = repo.linux_patch_get_version(repo[victim])
            tmp[version].add(victim)
        victims = tmp
        maintainers_version = load_maintainers(config, victims.keys())
    else:
        config.load_ccache_mbox()
        characteristics, maintainers_version = load_characteristics_and_maintainers(config, clustering)
        all_message_ids = get_relevant_patches(characteristics)
        if bulk:
            victims = random.sample(all_message_ids, bulk)
        else:
            victims = [random.choice(all_message_ids)]

    # create temporary directory infrastructure
    d_tmp = tempfile.mkdtemp()
    for d in linux_directory_skeleton:
        mkdir(join(d_tmp, d))

    for file in linux_file_skeleton:
        Path(join(d_tmp, file)).touch()

    accepted = 0
    declined = 0
    skipped = 0
    errors = 0
    try:
        for version, message_ids in victims.items():
            # build the structure anew for every different version
            repo_get_and_write_file(repo, version, 'MAINTAINERS', d_tmp)
            repo_get_and_write_file(repo, version, 'scripts/get_maintainer.pl', d_tmp)
            linux_maintainers = maintainers_version[version]

            for message_id in message_ids:
                log.info('Processing %s (%s)' % (message_id, version))
                message_raw = repo.mbox.get_raws(message_id)[0]

                if b'Content-Transfer-Encoding: base64' in message_raw:
                    log.error('Detected base64 encoded mail, skipping it silently')
                    skipped += 1
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
                    skipped += 1
                    continue

                if pl.returncode != 0 or pl_output == '\n\n':
                    log.error('Unknown error while executing perl script, skipping')
                    errors += 1
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
                        pasta_people.add((reviewer[1].lower(), 'reviewer'))

                    for maintainer in maintainers:
                        mtr_mail = maintainer[1].lower()
                        # Pia, wie kann das passieren, dass das leer ist? Bzw. wann?
                        if mtr_mail == '' or mtr_mail == 'torvalds@linux-foundation.org':
                            continue

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
                        pasta_people.add((maintainer[1].lower(), status))

                log.info('maintainers successfully retrieved by PaStA')

                pl_split = pl_output.split('\n')
                pl_people = pl_split[0].split(';')
                pl_subsystems = set(pl_split[2].split(';'))

                # pl_people will contain lists. Filter them.
                pl_lists = {list.split(' ')[0] for list in pl_people if ' list' in list}
                pl_people = {person for person in pl_people if ' list' not in person}

                # First, check if subsystems actually match. Unfortunately,
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
                        match = pl_system_regex.match(pl_person)
                        if not match:
                            raise ValueError('regex did not match for person %s from message_id %s'
                                             % (pl_person, message_id))

                    triple = match.group(1).lower(), match.group(2).lower()

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

        log.info('Skipped patches: %u' % skipped)
        log.info('Errors: %u' % errors)
        total = accepted + declined
        log.info('Total parseable patches: %u' % total)
        log.info('  %u (%.2f%%) passed comparisons' % (accepted, accepted * 100 / total))
        log.info('  %u (%.2f%%) failed comparisons' % (declined, declined * 100 / total))
    finally:
        shutil.rmtree(d_tmp)
