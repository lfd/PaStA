from pypasta import LinuxMailCharacteristics
from pypasta.LinuxMaintainers import load_maintainers, LinuxSubsystem
import os
import subprocess
import shutil
from pathlib import Path
from logging import getLogger
from git import Git

log = getLogger(__name__[-15:])


def compare_getmaintainers(config, prog, argv):
    print("Empty Skeleton")
