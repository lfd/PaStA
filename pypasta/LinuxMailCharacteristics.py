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
_clustering = None

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')
VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')

MAILING_LISTS = {'alsa-devel@alsa-project.org', 'amd-gfx@lists.freedesktop.org', 'apparmor@lists.ubuntu.com',
                 'ath10k@lists.infradead.org', 'autofs@vger.kernel.org', 'b43-dev@lists.infradead.org',
                 'b.a.t.m.a.n@lists.open-mesh.org', 'blinux-list@redhat.com', 'bpf@vger.kernel.org',
                 'bridge@lists.linux-foundation.org', 'cake@lists.bufferbloat.net', 'ceph-devel@vger.kernel.org',
                 'cgroups@vger.kernel.org', 'cip-dev@lists.cip-project.org', 'clang-built-linux@googlegroups.com',
                 'cluster-devel@redhat.com', 'cocci@systeme.lip6.fr', 'dccp@vger.kernel.org',
                 'devel@acpica.org', 'devel@lists.orangefs.org', 'devicetree@vger.kernel.org',
                 'dmaengine@vger.kernel.org', 'dm-devel@redhat.com', 'drbd-dev@lists.linbit.com',
                 'dri-devel@lists.freedesktop.org', 'driverdev-devel@linuxdriverproject.org', 'ecryptfs@vger.kernel.org',
                 'etnaviv@lists.freedesktop.org', 'freedreno@lists.freedesktop.org', 'greybus-dev@lists.linaro.org',
                 'ibm-acpi-devel@lists.sourceforge.net', 'industrypack-devel@lists.sourceforge.net', 'intel-gfx@lists.freedesktop.org',
                 'intel-gvt-dev@lists.freedesktop.org', 'intel-wired-lan@osuosl.org', 'iommu@lists.linux-foundation.org',
                 'io-uring@vger.kernel.org', 'isdn4linux@listserv.isdn4linux.de', 'jailhouse-dev@googlegroups.com',
                 'jfs-discussion@lists.sourceforge.net', 'kasan-dev@googlegroups.com', 'kernel-hardening@lists.openwall.com',
                 'kernel-janitors@vger.kernel.org', 'kexec@lists.infradead.org', 'keyrings@vger.kernel.org',
                 'kgdb-bugreport@lists.sourceforge.net', 'ksummit-discuss@lists.linuxfoundation.org', 'kvmarm@lists.cs.columbia.edu',
                 'kvm-ppc@vger.kernel.org', 'kvm@vger.kernel.org', 'legousb-devel@lists.sourceforge.net',
                 'libertas-dev@lists.infradead.org', 'linaro-mm-sig@lists.linaro.org', 'linux1394-devel@lists.sourceforge.net',
                 'linux-acpi@vger.kernel.org', 'linux-afs@lists.infradead.org', 'linux-alpha@vger.kernel.org',
                 'linux-amlogic@lists.infradead.org', 'linux-api@vger.kernel.org', 'linux-arch@vger.kernel.org',
                 'linux-arm-kernel@lists.infradead.org', 'linux-arm-msm@vger.kernel.org', 'linux-aspeed@lists.ozlabs.org',
                 'linux-audit@redhat.com', 'linux-bcache@vger.kernel.org', 'linux-block@vger.kernel.org',
                 'linux-bluetooth@vger.kernel.org', 'linux-btrfs@vger.kernel.org', 'linux-cachefs@redhat.com',
                 'linux-can@vger.kernel.org', 'linux-cifs@vger.kernel.org', 'linux-clk@vger.kernel.org',
                 'linux-crypto@vger.kernel.org', 'linux-csky@vger.kernel.org', 'linux-decnet-user@lists.sourceforge.net',
                 'linux-doc@vger.kernel.org', 'linux-edac@vger.kernel.org', 'linux-efi@vger.kernel.org',
                 'linux-embedded@vger.kernel.org', 'linux-erofs@lists.ozlabs.org', 'linux-ext4@vger.kernel.org',
                 'linux-f2fs-devel@lists.sourceforge.net', 'linux-fbdev@vger.kernel.org', 'linux-fpga@vger.kernel.org',
                 'linux-fscrypt@vger.kernel.org', 'linux-fsdevel@vger.kernel.org', 'linux-gpio@vger.kernel.org',
                 'linux-hams@vger.kernel.org', 'linux-hexagon@vger.kernel.org', 'linux-hwmon@vger.kernel.org',
                 'linux-hyperv@vger.kernel.org', 'linux-i2c@vger.kernel.org', 'linux-i3c@lists.infradead.org',
                 'linux-ia64@vger.kernel.org', 'linux-ide@vger.kernel.org', 'linux-iio@vger.kernel.org',
                 'linux-input@vger.kernel.org', 'linux-integrity@vger.kernel.org', 'linux-kbuild@vger.kernel.org',
                 'linux-kselftest@vger.kernel.org', 'linux-leds@vger.kernel.org', 'linux-m68k@vger.kernel.org',
                 'linux-man@vger.kernel.org', 'linux-mediatek@lists.infradead.org', 'linux-media@vger.kernel.org',
                 'linux-mips@vger.kernel.org', 'linux-mmc@vger.kernel.org', 'linux-mm@kvack.org',
                 'linux-modules@vger.kernel.org', 'linux-mtd@lists.infradead.org', 'linux-next@vger.kernel.org',
                 'linux-nfc@lists.01.org', 'linux-nfs@vger.kernel.org', 'linux-nilfs@vger.kernel.org',
                 'linux-ntb@googlegroups.com', 'linux-ntfs-dev@lists.sourceforge.net', 'linux-nvdimm@lists.01.org',
                 'linux-nvme@lists.infradead.org', 'linux-omap@vger.kernel.org', 'linux-oxnas@groups.io',
                 'linux-parisc@vger.kernel.org', 'linux-parport@lists.infradead.org', 'linux-pci@vger.kernel.org',
                 'linux-pm@vger.kernel.org', 'linuxppc-dev@lists.ozlabs.org', 'linuxppc-users@lists.ozlabs.org',
                 'linux-ppp@vger.kernel.org', 'linux-pwm@vger.kernel.org', 'linux-raid@vger.kernel.org',
                 'linux-rdma@vger.kernel.org', 'linux-remoteproc@vger.kernel.org', 'linux-renesas-soc@vger.kernel.org',
                 'linux-riscv@lists.infradead.org', 'linux-rockchip@lists.infradead.org', 'linux-rpi-kernel@lists.infradead.org',
                 'linux-rtc@vger.kernel.org', 'linux-s390@vger.kernel.org', 'linux-samsung-soc@vger.kernel.org',
                 'linux-scsi@vger.kernel.org', 'linux-sctp@vger.kernel.org', 'linux-security-module@vger.kernel.org',
                 'linux-serial@vger.kernel.org', 'linux-sgx@vger.kernel.org', 'linux-sh@vger.kernel.org',
                 'linux-snps-arc@lists.infradead.org', 'linux-sparse@vger.kernel.org', 'linux-spdx@vger.kernel.org',
                 'linux-spi@vger.kernel.org', 'linux-stm32@st-md-mailman.stormreply.com', 'linux-tegra@vger.kernel.org',
                 'linux-tip-commits@vger.kernel.org', 'linux-trace-devel@vger.kernel.org', 'linux-um@lists.infradead.org',
                 'linux-unionfs@vger.kernel.org', 'linux-unisoc@lists.infradead.org', 'linux-usb@vger.kernel.org',
                 'linux-uvc-devel@lists.sourceforge.net', 'linux-watchdog@vger.kernel.org', 'linux-wireless@vger.kernel.org',
                 'linux-wpan@vger.kernel.org', 'linux-xfs@vger.kernel.org', 'linux-xtensa@linux-xtensa.org',
                 'live-patching@vger.kernel.org', 'lkml@vger.kernel.org', 'ltp@lists.linux.it',
                 'lvs-devel@vger.kernel.org', 'mjpeg-users@lists.sourceforge.net', 'nbd@other.debian.org',
                 'netdev@vger.kernel.org', 'netem@lists.linux-foundation.org', 'netfilter-devel@vger.kernel.org',
                 'nouveau@lists.freedesktop.org', 'openbmc@lists.ozlabs.org', 'openipmi-developer@lists.sourceforge.net',
                 'open-iscsi@googlegroups.com', 'openrisc@lists.librecores.org', 'openwrt-devel@lists.openwrt.org',
                 'oprofile-list@lists.sourceforge.net', 'osmocom-net-gprs@lists.osmocom.org', 'osst-users@lists.sourceforge.net',
                 'platform-driver-x86@vger.kernel.org', 'pvrusb2@isely.net', 'qemu-devel@nongnu.org',
                 'rcu@vger.kernel.org', 'reiserfs-devel@vger.kernel.org', 'samba-technical@lists.samba.org',
                 'selinux@vger.kernel.org', 'sparclinux@vger.kernel.org', 'speakup@linux-speakup.org',
                 'spice-devel@lists.freedesktop.org', 'squashfs-devel@lists.sourceforge.net', 'stable@vger.kernel.org',
                 'target-devel@vger.kernel.org', 'tboot-devel@lists.sourceforge.net', 'tipc-discussion@lists.sourceforge.net',
                 'tomoyo-users-en@lists.osdn.me', 'tomoyo-users@lists.osdn.me', 'tpmdd-devel@lists.sourceforge.net',
                 'uboot-stm32@st-md-mailman.stormreply.com', 'usb-storage@lists.one-eyed-alien.net', 'usrp-users@lists.ettus.com',
                 'util-linux@vger.kernel.org', 'v9fs-developer@lists.sourceforge.net', 'virtualization@lists.linux-foundation.org',
                 'wcn36xx@lists.infradead.org', 'wireguard@lists.zx2c4.com', 'workflows@vger.kernel.org',
                 'xdp-newbies@vger.kernel.org', 'xen-devel@lists.xenproject.org'}


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


class MaintainerMetrics:
    def __init__(self, c):
        self.all_lists_one_mtr_per_sec = False
        self.one_list_and_mtr = False
        self.one_list_mtr_per_sec = False
        self.one_list = False
        self.one_list_or_mtr = False

        # Metric: All lists + at least one maintainer per section
        # needs to be addressed correctly
        if (not c.mtrs_has_lists or c.mtrs_has_list_per_section) and \
           (not c.mtrs_has_maintainers or c.mtrs_has_maintainer_per_section):
            self.all_lists_one_mtr_per_sec = True

        # Metric: At least one correct list + at least one correct maintainer
        if (not c.mtrs_has_lists or c.mtrs_has_one_correct_list) and \
           (not c.mtrs_has_maintainers or c.mtrs_has_one_correct_maintainer):
            self.one_list_and_mtr = True

        # Metric: One correct list + one maintainer per section
        if (not c.mtrs_has_lists or c.mtrs_has_one_correct_list) and c.mtrs_has_maintainer_per_section:
            self.one_list_mtr_per_sec = True

        # Metric: One correct list
        if not c.mtrs_has_lists or c.mtrs_has_one_correct_list:
            self.one_list = True

        # Metric: One correct list or one correct maintainer
        if c.mtrs_has_lists and c.mtrs_has_one_correct_list:
            self.one_list_or_mtr = True
        elif c.mtrs_has_maintainers and c.mtrs_has_one_correct_maintainer:
            self.one_list_or_mtr = True
        if not c.mtrs_has_lists and not c.mtrs_has_maintainers:
            self.one_list_or_mtr = c.mtrs_has_linux_kernel


class LinuxMailCharacteristics:
    BOTS = {'tip-bot2@linutronix.de', 'tipbot@zytor.com',
            'noreply@ciplatform.org', 'patchwork@emeril.freedesktop.org'}
    POTENTIAL_BOTS = {'broonie@kernel.org', 'lkp@intel.com'}

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
        email = self.mail_from[1].lower()
        subject = email_get_header_normalised(message, 'subject')
        uagent = email_get_header_normalised(message, 'user-agent')
        xmailer = email_get_header_normalised(message, 'x-mailer')
        x_pw_hint = email_get_header_normalised(message, 'x-patchwork-hint')
        potential_bot = email in LinuxMailCharacteristics.POTENTIAL_BOTS

        if email in LinuxMailCharacteristics.BOTS:
            return True

        if potential_bot:
            if x_pw_hint == 'ignore':
                return True

            # Mark Brown's bot and lkp
            if subject.startswith('applied'):
                return True

        if LinuxMailCharacteristics.REGEX_GREG_ADDED.match(subject):
            return True

        # AKPM's bot. AKPM uses s-nail for automated mails, and sylpheed for
        # all other mails. That's how we can easily separate automated mails
        # from real mails. Secondly, akpm acts as bot if the subject contains [merged]
        if email == 'akpm@linux-foundation.org':
            if 's-nail' in uagent or '[merged]' in subject:
                return True
            if 'mm-commits@vger.kernel.org' in self.lists:
                return True

        # syzbot - email format: syzbot-hash@syzkaller.appspotmail.com
        if 'syzbot' in email and 'syzkaller.appspotmail.com' in email:
            return True

        if xmailer == 'tip-git-log-daemon':
            return True

        # Stephen Rothwell's automated emails (TBD: generates false positives)
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

    def _get_maintainer(self, maintainer, patch):
        sections = maintainer.get_sections_by_files(patch.diff.affected)
        for section in sections:
            s_lists, s_maintainers, s_reviewers = maintainer.get_maintainers(section)
            s_maintainers = {x[1] for x in s_maintainers if x[1]}
            s_reviewers = {x[1] for x in s_reviewers if x[1]}
            self.maintainers[section] = s_lists, s_maintainers, s_reviewers

        self.mtrs_has_lists = False
        self.mtrs_has_maintainers = False
        self.mtrs_has_one_correct_list = False
        self.mtrs_has_one_correct_maintainer = False
        self.mtrs_has_maintainer_per_section = True
        self.mtrs_has_list_per_section = True
        self.mtrs_has_linux_kernel = 'linux-kernel@vger.kernel.org' in self.recipients_lists

        recipients = self.recipients_lists | self.recipients_other | \
                     {self.mail_from[1]}
        recipients = ignore_tlds(recipients)
        for section, (s_lists, s_maintainers, s_reviewers) in self.maintainers.items():
            if section == 'THE REST':
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
                self.mtrs_has_maintainer_per_section = False

            if len(s_lists) and len(s_lists & recipients) == 0:
                self.mtrs_has_list_per_section = False

        self.maintainer_metrics = MaintainerMetrics(self)

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

    def _is_next(self):
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

    def list_matches_patch(self, list):
        for lists, _, _ in self.maintainers.values():
            if list in lists:
                return True
        return False

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
        self.mtrs_has_maintainer_per_section = None
        self.mtrs_has_list_per_section = None
        self.mtrs_has_linux_kernel = None
        self.maintainer_metrics = None

        message = repo.mbox.get_messages(message_id)[0]
        thread = repo.mbox.threads.get_thread(message_id)
        recipients = email_get_recipients(message)

        self.recipients_lists = recipients & MAILING_LISTS
        self.recipients_other = recipients - MAILING_LISTS

        self.mail_from = email_get_from(message)
        self.subject = email_get_header_normalised(message, 'Subject')
        self.date = mail_parse_date(message['Date'])

        self.lists = repo.mbox.get_lists(message_id)
        self.is_next = self._is_next()

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
                self.linux_version = repo.linux_patch_get_version(patch)

                if clustering is not None:
                    self.is_upstream = len(clustering.get_upstream(message_id)) != 0

                processes = ['linux-next', 'git pull', 'rfc']
                self.process_mail = True in [process in self.subject for process in processes]

                if maintainers_version is not None:
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
