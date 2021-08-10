"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from .MailCharacteristics import MailCharacteristics, PatchType


class UBootMailCharacteristics(MailCharacteristics):
    ROOT_DIRS = ['.github/',
                 'api/',
                 'api_examples/',
                 'arch/',
                 'board/',
                 'cmd/',
                 'common/',
                 'configs/',
                 'cpu/',
                 'disk/',
                 'doc/',
                 'Documentation/',
                 'drivers/',
                 'dts/',
                 'dtt/',
                 'env/',
                 'examples/',
                 'fs/',
                 'include/',
                 'lib/',
                 'lib_arm/',
                 'lib_avr32/',
                 'lib_blackfin/',
                 'libfdt/',
                 'lib_generic/',
                 'lib_i386/',
                 'lib_m68k/',
                 'lib_microblaze/',
                 'lib_mips/',
                 'lib_nios/',
                 'lib_nios2/',
                 'lib_ppc/',
                 'lib_sh/',
                 'lib_sparc/',
                 'Licenses/',
                 'mmc_spl/',
                 'nand_spl/',
                 'net/',
                 'onenand_ipl/',
                 'post/',
                 'rtc/',
                 'scripts/',
                 'spl/',
                 'test/',
                 'tools/',
    ]
    ROOT_FILES = ['.azure-pipelines.yml',
                  '.checkpatch.conf',
                  '.git',
                  '.gitattributes',
                  '.gitignore',
                  '.gitlab-ci.yml',
                  '.mailmap',
                  '.readthedocs.yml',
                  '.travis.yml',
                  'arm_config.mk',
                  'avr32_config.mk',
                  'blackfin_config.mk',
                  'boards.cfg',
                  'CHANGELOG',
                  'CHANGELOG-before-U-Boot-1.1.5',
                  'config.mk',
                  'COPYING',
                  'CREDITS',
                  'helper.mk',
                  'i386_config.mk',
                  'Kbuild',
                  'Kconfig',
                  'm68k_config.mk',
                  'MAINTAINERS',
                  'MAKEALL',
                  'Makefile',
                  'microblaze_config.mk',
                  'mips_config.mk',
                  'mkconfig',
                  'nios2_config.mk',
                  'nios_config.mk',
                  'ppc_config.mk',
                  'README',
                  'README.imx31',
                  'README.nios_CONFIG_SYS_NIOS_CPU',
                  'rules.mk',
                  'sh_config.mk',
                  'snapshot.commit',
                  'sparc_config.mk',
    ]

    HAS_MAINTAINERS = True

    # Additional lists that are not known by pasta
    LISTS = set()

    def __init__(self, repo, maintainers_version, clustering, message_id):
        super().__init__(repo, clustering, message_id)
        self.__init()
        self._cleanup(maintainers_version)

    def __init(self):
        if self.is_from_bot:
            self.type = PatchType.BOT

        if not self.is_patch:
            return

        if self.type == PatchType.OTHER:
            self.type = PatchType.PATCH
