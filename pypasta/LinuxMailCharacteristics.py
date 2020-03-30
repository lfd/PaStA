"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019-2020

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import email
import re

from anytree import LevelOrderIter
from logging import getLogger
from multiprocessing import Pool, cpu_count

from .Util import mail_parse_date, load_pkl_and_update


log = getLogger(__name__[-15:])

_repo = None
_maintainers_version = None
_mainline_tags = None
_clustering = None

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')
MAINLINE_REGEX = re.compile(r'^v(\d+\.\d+|2\.6\.\d+)(-rc\d+)?$')
VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')

MAILING_LISTS = {'devel@acpica.org', 'alsa-devel@alsa-project.org', 'clang-built-linux@googlegroups.com',
                 'jailhouse-dev@googlegroups.com', 'kasan-dev@googlegroups.com', 'linux-ntb@googlegroups.com',
                 'open-iscsi@googlegroups.com', 'linux-oxnas@groups.io', 'pvrusb2@isely.net',
                 'driverdev-devel@linuxdriverproject.org', 'speakup@linux-speakup.org', 'linux-xtensa@linux-xtensa.org',
                 'linux-nfc@lists.01.org', 'linux-nvdimm@lists.01.org', 'cake@lists.bufferbloat.net',
                 'kvmarm@lists.cs.columbia.edu', 'isdn4linux@listserv.isdn4linux.de', 'usrp-users@lists.ettus.com',
                 'amd-gfx@lists.freedesktop.org', 'dri-devel@lists.freedesktop.org', 'etnaviv@lists.freedesktop.org',
                 'freedreno@lists.freedesktop.org', 'intel-gfx@lists.freedesktop.org',
                 'intel-gvt-dev@lists.freedesktop.org', 'nouveau@lists.freedesktop.org',
                 'spice-devel@lists.freedesktop.org', 'ath10k@lists.infradead.org', 'b43-dev@lists.infradead.org',
                 'kexec@lists.infradead.org', 'libertas-dev@lists.infradead.org', 'linux-afs@lists.infradead.org',
                 'linux-amlogic@lists.infradead.org', 'linux-arm-kernel@lists.infradead.org',
                 'linux-i3c@lists.infradead.org', 'linux-mediatek@lists.infradead.org', 'linux-mtd@lists.infradead.org',
                 'linux-nvme@lists.infradead.org', 'linux-parport@lists.infradead.org',
                 'linux-riscv@lists.infradead.org', 'linux-rockchip@lists.infradead.org',
                 'linux-rpi-kernel@lists.infradead.org', 'linux-snps-arc@lists.infradead.org',
                 'linux-um@lists.infradead.org', 'linux-unisoc@lists.infradead.org', 'wcn36xx@lists.infradead.org',
                 'openrisc@lists.librecores.org', 'greybus-dev@lists.linaro.org', 'linaro-mm-sig@lists.linaro.org',
                 'drbd-dev@lists.linbit.com', 'bridge@lists.linux-foundation.org', 'iommu@lists.linux-foundation.org',
                 'linux-next@vger.kernel.org', 'netem@lists.linux-foundation.org',
                 'virtualization@lists.linux-foundation.org', 'ltp@lists.linux.it',
                 'usb-storage@lists.one-eyed-alien.net', 'b.a.t.m.a.n@lists.open-mesh.org',
                 'kernel-hardening@lists.openwall.com', 'openwrt-devel@lists.openwrt.org', 'devel@lists.orangefs.org',
                 'tomoyo-users@lists.osdn.me', 'tomoyo-users-en@lists.osdn.me', 'osmocom-net-gprs@lists.osmocom.org',
                 'linux-aspeed@lists.ozlabs.org', 'linux-erofs@lists.ozlabs.org', 'linuxppc-dev@lists.ozlabs.org',
                 'linuxppc-users@lists.ozlabs.org', 'openbmc@lists.ozlabs.org', 'samba-technical@lists.samba.org',
                 'ibm-acpi-devel@lists.sourceforge.net', 'industrypack-devel@lists.sourceforge.net',
                 'jfs-discussion@lists.sourceforge.net', 'kgdb-bugreport@lists.sourceforge.net',
                 'linux1394-devel@lists.sourceforge.net', 'linux-decnet-user@lists.sourceforge.net',
                 'linux-f2fs-devel@lists.sourceforge.net', 'linux-ntfs-dev@lists.sourceforge.net',
                 'linux-uvc-devel@lists.sourceforge.net', 'mjpeg-users@lists.sourceforge.net',
                 'openipmi-developer@lists.sourceforge.net', 'oprofile-list@lists.sourceforge.net',
                 'osst-users@lists.sourceforge.net', 'squashfs-devel@lists.sourceforge.net',
                 'tboot-devel@lists.sourceforge.net', 'tipc-discussion@lists.sourceforge.net',
                 'v9fs-developer@lists.sourceforge.net', 'apparmor@lists.ubuntu.com', 'xen-devel@lists.xenproject.org',
                 'qemu-devel@nongnu.org', 'intel-wired-lan@osuosl.org', 'nbd@other.debian.org',
                 'blinux-list@redhat.com', 'cluster-devel@redhat.com', 'dm-devel@redhat.com', 'linux-audit@redhat.com',
                 'linux-cachefs@redhat.com', 'linux-stm32@st-md-mailman.stormreply.com',
                 'uboot-stm32@st-md-mailman.stormreply.com', 'cocci@systeme.lip6.fr', 'autofs@vger.kernel.org',
                 'bpf@vger.kernel.org', 'ceph-devel@vger.kernel.org', 'cgroups@vger.kernel.org', 'dccp@vger.kernel.org',
                 'devicetree@vger.kernel.org', 'dmaengine@vger.kernel.org', 'ecryptfs@vger.kernel.org',
                 'kernel-janitors@vger.kernel.org', 'keyrings@vger.kernel.org', 'kvm@vger.kernel.org',
                 'kvm-ppc@vger.kernel.org', 'linux-acpi@vger.kernel.org', 'linux-alpha@vger.kernel.org',
                 'linux-api@vger.kernel.org', 'linux-arch@vger.kernel.org', 'linux-arm-msm@vger.kernel.org',
                 'linux-bcache@vger.kernel.org', 'linux-block@vger.kernel.org', 'linux-bluetooth@vger.kernel.org',
                 'linux-btrfs@vger.kernel.org', 'linux-can@vger.kernel.org', 'linux-cifs@vger.kernel.org',
                 'linux-clk@vger.kernel.org', 'linux-crypto@vger.kernel.org', 'linux-csky@vger.kernel.org',
                 'linux-doc@vger.kernel.org', 'linux-edac@vger.kernel.org', 'linux-efi@vger.kernel.org',
                 'linux-embedded@vger.kernel.org', 'linux-ext4@vger.kernel.org', 'linux-fbdev@vger.kernel.org',
                 'linux-fpga@vger.kernel.org', 'linux-fscrypt@vger.kernel.org', 'linux-fsdevel@vger.kernel.org',
                 'linux-gpio@vger.kernel.org', 'linux-hams@vger.kernel.org', 'linux-hexagon@vger.kernel.org',
                 'linux-hwmon@vger.kernel.org', 'linux-hyperv@vger.kernel.org', 'linux-i2c@vger.kernel.org',
                 'linux-ia64@vger.kernel.org', 'linux-ide@vger.kernel.org', 'linux-iio@vger.kernel.org',
                 'linux-input@vger.kernel.org', 'linux-integrity@vger.kernel.org', 'linux-kbuild@vger.kernel.org',
                 'linux-kernel@vger.kernel.org', 'linux-kselftest@vger.kernel.org', 'linux-leds@vger.kernel.org',
                 'linux-man@vger.kernel.org', 'linux-media@vger.kernel.org', 'linux-mips@vger.kernel.org',
                 'linux-mmc@vger.kernel.org', 'linux-modules@vger.kernel.org', 'linux-next@vger.kernel.org',
                 'linux-nfs@vger.kernel.org', 'linux-nilfs@vger.kernel.org', 'linux-omap@vger.kernel.org',
                 'linux-parisc@vger.kernel.org', 'linux-pci@vger.kernel.org', 'linux-pm@vger.kernel.org',
                 'linux-ppp@vger.kernel.org', 'linux-pwm@vger.kernel.org', 'linux-raid@vger.kernel.org',
                 'linux-rdma@vger.kernel.org', 'linux-remoteproc@vger.kernel.org', 'linux-renesas-soc@vger.kernel.org',
                 'linux-rtc@vger.kernel.org', 'linux-s390@vger.kernel.org', 'linux-samsung-soc@vger.kernel.org',
                 'linux-scsi@vger.kernel.org', 'linux-sctp@vger.kernel.org', 'linux-security-module@vger.kernel.org',
                 'linux-serial@vger.kernel.org',  'linux-sgx@vger.kernel.org', 'linux-sh@vger.kernel.org',
                 'linux-sparse@vger.kernel.org', 'linux-spi@vger.kernel.org', 'linux-tegra@vger.kernel.org',
                 'linux-tip-commits@vger.kernel.org', 'linux-trace-devel@vger.kernel.org',
                 'linux-unionfs@vger.kernel.org', 'linux-usb@vger.kernel.org', 'linux-watchdog@vger.kernel.org',
                 'linux-wireless@vger.kernel.org', 'linux-wpan@vger.kernel.org', 'linux-xfs@vger.kernel.org',
                 'live-patching@vger.kernel.org', 'lvs-devel@vger.kernel.org', 'netdev@vger.kernel.org',
                 'netfilter-devel@vger.kernel.org', 'platform-driver-x86@vger.kernel.org',
                 'reiserfs-devel@vger.kernel.org', 'selinux@vger.kernel.org', 'sparclinux@vger.kernel.org',
                 'stable@vger.kernel.org','target-devel@vger.kernel.org', 'util-linux@vger.kernel.org',
                 'xdp-newbies@vger.kernel.org'}


def email_get_recipients(message):
    recipients = message.get_all('To', []) + message.get_all('Cc', [])
    recipients = list(filter(None, recipients))
    # get_all might return Header objects. Convert them all to strings.
    recipients = [str(x) for x in recipients]

    # Only accept valid email addresses
    recipients = {x[1].lower() for x in email.utils.getaddresses(recipients)
                  if VALID_EMAIL_REGEX.match(x[1])}

    return recipients


def email_get_header_normalised(message, header):
    header = str(message[header] or '').lower()
    header = header.replace('\n', '').replace('\t', ' ')

    return header


def email_get_from(message):
    mail_from = email_get_header_normalised(message, 'From')
    return email.utils.parseaddr(mail_from)


def ignore_tld(address):
    match = MAIL_STRIP_TLD_REGEX.match(address)
    if match:
        return match.group(1)

    return address


def ignore_tlds(addresses):
    return {ignore_tld(address) for address in addresses if address}


class LinuxMailCharacteristics:
    REGEX_COMMIT_UPSTREAM = re.compile('.*commit\s+.+\s+upstream.*', re.DOTALL | re.IGNORECASE)
    REGEX_COVER = re.compile('\[.*patch.*\s0+/.*\].*', re.IGNORECASE)
    REGEX_GREG_ADDED = re.compile('patch \".*\" added to .*')
    ROOT_FILES = ['.clang-format',
                  '.cocciconfig',
                  '.get_maintainer.ignore',
                  '.gitignore',
                  '.gitattributes',
                  '.mailmap',
                  'COPYING',
                  'CREDITS',
                  'Kbuild',
                  'Kconfig',
                  'README',
                  'MAINTAINERS',
                  'Makefile']
    ROOT_DIRS = ['Documentation/',
                 'LICENSES/',
                 'arch/',
                 'block/',
                 'certs/',
                 'crypto/',
                 'drivers/',
                 'fs/',
                 'include/',
                 'init/',
                 'ipc/',
                 'kernel/',
                 'lib/',
                 'mm/',
                 'net/',
                 'samples/',
                 'scripts/',
                 'security/',
                 'sound/',
                 'tools/',
                 'usr/',
                 'virt/',
                 # not yet merged subsystems
                 'kunit/']

    def _is_from_bot(self, message):
        email = self.mail_from[1]
        bots = ['broonie@kernel.org', 'lkp@intel.com']
        potential_bot = True in [bot in email for bot in bots]

        if message['X-Patchwork-Hint'] == 'ignore' and potential_bot:
            return True

        subject = str(message['Subject']).lower()

        if potential_bot and subject.startswith('applied'):
            return True

        if LinuxMailCharacteristics.REGEX_GREG_ADDED.match(subject):
            return True

        # syzbot
        if 'syzbot' in email and 'syzkaller.appspotmail.com' in email:
            return True

        # The Tip bot
        if 'tipbot@zytor.com' in email or \
           'noreply@ciplatform.org' in email:
            return True

        if message['X-Mailer'] == 'tip-git-log-daemon':
            return True

        # Stephen Rothwell's automated emails
        if self.is_next and 'sfr@canb.auug.org.au' in email:
            return True

        return False

    def _has_foreign_response(self, repo, thread):
        """
        This function will return True, if there's another author in this
        thread, other than the ORIGINAL author. (NOT the author of this
        email)
        """
        if len(thread.children) == 0:
            return False  # If there is no response the check is trivial

        for mail in list(LevelOrderIter(thread)):
            # Beware, the mail might be virtual
            if mail.name not in repo:
                continue

            this_email = email_get_from(repo.mbox.get_messages(mail.name)[0])[1]
            if this_email != self.mail_from[1]:
                return True
        return False

    def _patch_get_version(self):
        tag = None

        for cand_tag, cand_tag_date in _mainline_tags:
            if cand_tag_date > self.date:
                break
            tag = cand_tag

        if tag is None:
            raise RuntimeError('No valid tag found for patch %s' % self.message_id)

        return tag

    def _get_maintainer(self, maintainer, patch):
        subsystems = maintainer.get_subsystems_by_files(patch.diff.affected)
        for subsystem in subsystems:
            s_lists, s_maintainers, s_reviewers = maintainer.get_maintainers(subsystem)
            s_maintainers = {x[1] for x in s_maintainers if x[1]}
            s_reviewers = {x[1] for x in s_reviewers if x[1]}
            self.maintainers[subsystem] = s_lists, s_maintainers, s_reviewers

        self.mtrs_has_lists = False
        self.mtrs_has_maintainers = False
        self.mtrs_has_one_correct_list = False
        self.mtrs_has_one_correct_maintainer = False
        self.mtrs_has_maintainer_per_subsystem = True
        self.mtrs_has_list_per_subsystem = True
        self.mtrs_has_linux_kernel = 'linux-kernel@vger.kernel.org' in self.recipients_lists

        recipients = self.recipients_lists | self.recipients_other | \
                     {self.mail_from[1]}
        recipients = ignore_tlds(recipients)
        for subsystem, (s_lists, s_maintainers, s_reviewers) in self.maintainers.items():
            if subsystem == 'THE REST':
                continue

            s_lists = ignore_tlds(s_lists)
            s_maintainers = ignore_tlds(s_maintainers) | ignore_tlds(s_reviewers)

            if len(s_lists):
                self.mtrs_has_lists = True

            if len(s_maintainers):
                self.mtrs_has_maintainers = True

            if len(s_lists & recipients):
                self.mtrs_has_one_correct_list = True

            if len(s_maintainers & recipients):
                self.mtrs_has_one_correct_maintainer = True

            if len(s_maintainers) and len(s_maintainers & recipients) == 0:
                self.mtrs_has_maintainer_per_subsystem = False

            if len(s_lists) and len(s_lists & recipients) == 0:
                self.mtrs_has_list_per_subsystem = False

    def _is_stable_review(self, message, patch):
        if 'X-Mailer' in message and \
           'LinuxStableQueue' in message['X-Mailer']:
               return True

        if 'X-stable' in message:
            xstable = message['X-stable'].lower()
            if xstable == 'commit' or xstable == 'review':
                return True

        # The patch needs to be sent to the stable list
        if not ('stable' in self.lists or
                'stable@vger.kernel.org' in self.recipients_lists):
            return False

        message_flattened = '\n'.join(patch.message).lower()

        if 'review patch' in message_flattened:
            return True

        if 'upstream commit' in message_flattened:
            return True

        # Greg uses this if the patch doesn't apply to a stable tree
        if 'the patch below does not apply to the' in message_flattened:
            return True

        if LinuxMailCharacteristics.REGEX_COMMIT_UPSTREAM.match(message_flattened):
            return True

        return False

    @staticmethod
    def _patches_linux(patch):
        for affected in patch.diff.affected:
            if True in map(lambda x: affected.startswith(x),
                           LinuxMailCharacteristics.ROOT_DIRS) or \
               affected in LinuxMailCharacteristics.ROOT_FILES:
                continue

            return False

        return True

    def _is_next(self, message):
        if 'linux-next' in self.lists:
            return True

        if 'linux-next@vger.kernel.org' in self.recipients_lists:
            return True

        return False

    def _analyse_series(self, thread, message):
        if self.is_patch:
            if self.message_id == thread.name or \
               self.message_id in [x.name for x in thread.children]:
                self.is_first_patch_in_thread = True
        elif 'Subject' in message and \
             LinuxMailCharacteristics.REGEX_COVER.match(str(message['Subject'])):
            self.is_cover_letter = True

    def __init__(self, repo, maintainers_version, clustering, message_id):
        self.message_id = message_id
        self.is_patch = message_id in repo and message_id not in repo.mbox.invalid
        self.is_stable_review = False
        self.patches_linux = False
        self.has_foreign_response = None
        self.is_upstream = None

        self.linux_version = None

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False
        self.process_mail = False

        # stuff for maintainers analysis
        self.maintainers = dict()
        self.mtrs_has_lists = None
        self.mtrs_has_maintainers = None
        self.mtrs_has_one_correct_list = None
        self.mtrs_has_one_correct_maintainer = None
        self.mtrs_has_maintainer_per_subsystem = None
        self.mtrs_has_list_per_subsystem = None
        self.mtrs_has_linux_kernel = None

        message = repo.mbox.get_messages(message_id)[0]
        thread = repo.mbox.threads.get_thread(message_id)
        recipients = email_get_recipients(message)

        self.recipients_lists = recipients & MAILING_LISTS
        self.recipients_other = recipients - MAILING_LISTS

        self.mail_from = email_get_from(message)
        self.subject = email_get_header_normalised(message, 'Subject')
        self.date = mail_parse_date(message['Date'])

        self.lists = repo.mbox.get_lists(message_id)
        self.is_next = self._is_next(message)

        self.is_from_bot = self._is_from_bot(message)
        self._analyse_series(thread, message)

        if self.is_patch:
            patch = repo[message_id]
            self.patches_linux = self._patches_linux(patch)
            self.is_stable_review = self._is_stable_review(message, patch)

            # We must only analyse foreign responses of patches if the patch is
            # the first patch in a thread. Otherwise, we might not be able to
            # determine the original author of a thread. Reason: That mail
            # might be missing.
            if self.is_first_patch_in_thread:
                self.has_foreign_response = self._has_foreign_response(repo, thread)

            if self.patches_linux:
                self.is_upstream = len(clustering.get_upstream(message_id)) != 0

                processes = ['linux-next', 'git pull', 'rfc']
                self.process_mail = True in [process in self.subject for process in processes]

                if maintainers_version is not None:
                    self.linux_version = self._patch_get_version()
                    maintainers = maintainers_version[self.linux_version]
                    self._get_maintainer(maintainers, patch)


def _load_mail_characteristic(message_id):
    return message_id, LinuxMailCharacteristics(_repo, _maintainers_version,
                                                _clustering, message_id)


def load_linux_mail_characteristics(config, maintainers_version, clustering,
                                    ids):
    repo = config.repo

    def _load_characteristics(ret):
        if ret is None:
            ret = dict()

        missing = ids - ret.keys()
        if len(missing) == 0:
            return ret, False

        global _mainline_tags
        _mainline_tags = list(filter(lambda x: MAINLINE_REGEX.match(x[0]),
                                     repo.tags))

        global _repo, _maintainers_version, _clustering
        _maintainers_version = maintainers_version
        _clustering = clustering
        _repo = repo
        p = Pool(processes=int(cpu_count()), maxtasksperchild=1)

        missing = p.map(_load_mail_characteristic, missing, chunksize=1000)
        missing = dict(missing)
        print('Done')
        p.close()
        p.join()
        _repo = None
        _maintainers_version = None
        _clustering = None

        return {**ret, **missing}, True

    log.info('Loading/Updating Linux patch characteristics...')
    characteristics = load_pkl_and_update(config.f_characteristics_pkl,
                                          _load_characteristics)

    return characteristics
