#!/bin/bash

LOCATION="ftp://ftp.kernel.org/pub/linux/kernel/projects/rt/"
STABLE_GIT="git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git"

BASEDIR=$PWD
FTPDST=$BASEDIR/rt-ftp
KERNELDST=$BASEDIR/linux
PATCHDIR=$BASEDIR/quilt-stacks

function die {
  echo "$@" 1>&2;
  exit -1;
}

function require {
  if [ -z $1 ]
  then
    die "error calling require()"
  else
    hash $1 &> /dev/null || die "Please install $1"
  fi
}
