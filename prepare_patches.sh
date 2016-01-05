#!/bin/bash

# Grund warum so kompliziert:
# Die RT-Git-Branches geben nicht genug informationen ueber vergangener
# Versionen her. Deshalb stellen wir uns einfach den Stand alle bekannter
# Versionen wieder selbst per Hand zusammen.
#
# Strategie:
# 1. Erstelle lokalen Mirror von _allen_ RT Sachen
# 2. Klone Linux Mainline
# 3. Entpacke die benoetigten Quilt Patches
# 4. Apply Patches
#    1. Erstelle analysis-rtversion branch der von der Basisversion abzweigt
#    2. Im Gaensemarsch mit Quilt einem nach dem anderen Patch applyen und Committen
#    
#
# Bemerkungen:
# zu 4.2: git quiltimport ist nur partiell moeglich, da viele Patche sehr kaputt
#         sind. Bei PreemptRT war es frueher gaengig, bei Patches keinen Autor
#         anzugeben. Wir verwenden dann einen "unknown" Platzhalter Autor.
#         Strategie:
#          1. Versuche, ob quiltimport erfolgreich ist
#          2. Wenn nicht, applye manuell
#         
#         Viele Patches kommen ohne Autor, Subject, Datum, ... Es wird dann 
#         beim Committen folgende Strategie verwendet:
#          - Leerer Autor?
#         

# We have to patch several old quilt patch stacks, as they are not readable by
# quiltimport: A 'content-type:' header inside the patch-mail confuses
# quiltimport (resp git mailinfo). Removing those headers fixes this issue.

# Issues with 3.0.1-rt9 and rt10:
# - The patch _paul_e__mckenney_-eliminate_-_rcu_boosted.patch contains 
#   doubleslashes which confuses quiltimport. Patch provided.

# notes: There are no quilt stacks for
# - 2.6.31
# - 2.6.33

# skipped for some other reasons:
# - 3.2.43-rt63-feat[12] (adds additional feature to a stable branch and is incremental to rt63, needs a special treatment)
# - 3.4.41-rt55-feat[123] (same as above)
# - 3.2-rc1-52e4c2a05-rt[12] (I don't know the patch base)

# Corruped recoverable versions:
# - 2.6.29-rc8-rt1 (minor failure, logo.gif fails to patch, this patch can be forced, fix provided)
# - 2.6.29-rc8-rt2 (see above, fix provided)

# Corrupted nonrecoverable versions:
# - 3.0.14-rt31 (Hunk failed, non recoverable, we have to skip this patch)

DOWNLOAD=false
CLONE_STABLE_KERNEL=false
UNPACK_PATCHES=false
BRANCH_AND_PATCH=false

HELP=true

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

function show_help {
  echo "$0: [-d] [-c] [-u] [-b]"
  echo "    -d : Create or update mirror of $LOCATION"
  echo "    -c : Clone or pull Linux stable Kernel $STABLE_GIT"
  echo "    -u : Unpack patches and prepare quilt stacks"
  echo "    -b : Apply all quilt patches"
  echo ""
  echo "First run -d, then -c, then -u, then -b or combine them"
  exit 0
}

####### SCRIPT START #######

# Required for downloading the Patches. Allows parallel downloads
require lftp
require git
require rsync
require quilt

while getopts "h?dcub" opt; do
  case "$opt" in
    h|\?)
      ;;

   d) DOWNLOAD=true
      HELP=false
      ;;

   c) CLONE_STABLE_KERNEL=true
      HELP=false
      ;;

   u) UNPACK_PATCHES=true
      HELP=false
      ;;

   b) BRANCH_AND_PATCH=true
      HELP=false
      ;;
  esac
done

if [[ "$HELP" = true ]] ; then
  show_help
fi

# Define list of versions where to strip the mismatched content-type headers
declare -a ContentTypeMismatch=(
2.6.22.1-rt2
2.6.22.1-rt4
2.6.22.1-rt5
2.6.22.1-rt6
2.6.22.1-rt7
2.6.22.1-rt8
2.6.22.1-rt9
2.6.23-rc1-rt0
2.6.23-rc1-rt1
2.6.23-rc1-rt2
2.6.23-rc1-rt3
2.6.23-rc1-rt4
2.6.23-rc1-rt5
2.6.23-rc1-rt6
2.6.23-rc1-rt7
2.6.23-rc2-rt1
2.6.23-rc2-rt2
2.6.23-rc4-rt1
2.6.23-rc8-rt1
2.6.23-rc9-rt1
2.6.23-rc9-rt2
2.6.23-rt1
2.6.23-rt2
2.6.23-rt3
)

if [ "$DOWNLOAD" = true ]
then
  mkdir -p $FTPDST-mirror || die "mkdir failed. check permissions"

  echo "syncing rt patch mirror..."
  lftp -e "mirror --continue --scan-all-first --depth-first --only-missing --parallel=10 --verbose ${LOCATION} ${FTPDST}-mirror ; exit" || die "downloading patches failed"

  rm -rf ${FTPDST} || die "rm ${FTPDST} failed"
  mkdir -p ${FTPDST} || die "mkdir failed. check permissions"

  echo "copying to local workdir..."
  rsync -r --include '*/' --include '*.xz' --exclude '*' ${FTPDST}-mirror/ ${FTPDST}/

  echo "unpacking patches..."
  # unpack everything else
  find $FTPDST -type f -name "*.xz" -print0 | xargs -n1 -P8 -0 xz -d -f

  echo "patch mirror up to date"
fi

if [ "$CLONE_STABLE_KERNEL" = true ]
then
  rm -rf ${KERNELDST} || die "git cleanup failed"
  if [ -d "${KERNELDST}-mirror/.git" ]
  then
    echo "mirror repo already existing, pulling..."
    cd ${KERNELDST}-mirror
    git pull || die "git pull failed"
    cd ..
  else
    echo "mirror repo not existing, cloning..."
    git clone ${STABLE_GIT} ${KERNELDST}-mirror || die "git clone failed"
  fi

  rm -rf ${KERNELDST} || die "error removing kernel workdir"
  echo "copying kernel to working directory..."
  cp -a ${KERNELDST}-mirror ${KERNELDST}
  echo "linux-stable git up to date"
fi

if [ "$UNPACK_PATCHES" = true ]
then
  echo "Unpacking quilt patchstacks"

  # cleanup
  rm -rf $PATCHDIR || die "rm failed"

  mkdir $PATCHDIR || die "mkdir failed"
  cd $PATCHDIR
  ls ${FTPDST} | xargs mkdir

  # Iterate over each folder
  #for version in $(find $PATCHDIR -maxdepth 1 -mindepth 1 -type d)
  for version in *
  do
    stacks=$(find $FTPDST/$version -name "*.tar")
    for i in $stacks
    do
      patchname=$(basename $i)
      rtversion=$(echo $patchname | sed -e 's/^patch\(\|es\)-//' | sed -e 's/\(-broken-out\|\)\.tar$//')
      baseversion=$(sed -e 's/-rt[0-9]\+\(\|-feat[0-9]\+\)$//' <<< $rtversion)

      # Skip certain patches (as mentioned above)
      # Additionally, skip all 3.x.y.z 'extended' versions (Where to get their sources??)
      if [[ ${baseversion} =~ ^3\.[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
         [[ ${rtversion} = "3.0.14-rt31" ]] ||
         [[ ${rtversion} =~ 3\.2\-rc1\-52e4c2a05\-rt[12]  ]] ||
         [[ ${rtversion} =~ 3\.2\.43\-rt63\-feat[12] ]] ||
         [[ ${rtversion} =~ 3\.4\.41\-rt55\-feat[123] ]]
      then
        echo "--- skipping version ${baseversion} <- ${rtversion} ---"
        continue
      fi

      echo "unpacking $rtversion"
      dstfolder=$PATCHDIR/$version/$rtversion
      mkdir $dstfolder &> /dev/null
      if [ $? = 0 ] ; then
        tar -xf $i -C $dstfolder || die "tar failed"
        mv $dstfolder/patches/* $dstfolder || die "mv failed"
        rm -rf $dstfolder/patches

        # Manually patch origin.patch.bz2 of versions 2.6.29-rc8-rt[12]
        if [[ ${rtversion} =~ ^2\.6\.29\-rc8\-rt[12]$ ]]; then
          echo "  -> Manually fixing ${rtversion}"
          rm ${dstfolder}/origin.patch.bz2
          bzcat ${BASEDIR}/fixes/${baseversion}-rt-origin.patch.bz2 > ${dstfolder}/origin.patch
          patch ${dstfolder}/series ${BASEDIR}/fixes/2.6.29-rc8-rt-series-fix.patch
        fi

        # Manually Fix 3.0.1-rt9,10 as they have // in their diffs which confuses quiltimport
        if [[ ${rtversion} =~ ^3\.0\.1\-rt(10|11)$ ]]; then
          echo "  -> Manually fixing ${rtversion}"
          patch ${dstfolder}/_paul_e__mckenney_-eliminate_-_rcu_boosted.patch \
                ${BASEDIR}/fixes/3.0.1-rt-_paul_e__mckenney_-eliminate_-_rcu_boosted.patch
        fi

        # Check if we have to strip the content-type: mail stuff
        for item in "${ContentTypeMismatch[@]}"; do
          if [ $item = $rtversion ]; then
            echo "  -> stripping errorneous content-type line..."
            find ${dstfolder} -type f -exec sed -i.old \{\} -e '/^Content-Type: multipart\/signed/d' \;\
                 -exec rm \{\}.old \;
          fi
        done
      else
        echo "  -> already existing, i'll just skip this one..."
      fi
    done
  done
  echo "quilt stacks sucessfully unpacked"
fi

if [ "$BRANCH_AND_PATCH" = true ]
then
  cd linux
  
  git reset --hard &> /dev/null || die "git reset failed"
  git clean -d -f -x &> /dev/null || die "git clean failed"

  for series in $(find $PATCHDIR -type f -name "series" | sort -V)
  do
    dir=$(dirname ${series})
    rtversion=${dir##*/}
    baseversion=$(sed -e 's/-rt[0-9]\+\(\|-feat[0-9]\+\)$//' <<< $rtversion)

    # special treatment for 3.12.0 and 3.14-0
    # ... There's absolutely no version nomenclature consistency in PreemptRT...
    if [ "$baseversion" = "3.12.0" ] || [ "$baseversion" = "3.14.0" ]; then
        baseversion=$(sed -e 's/\.0$//' <<< $baseversion)
    fi

    # Checkout analysis branch based on mainline version
    echo "Working on $rtversion..."
    git checkout -b analysis-${rtversion} v${baseversion} &> /dev/null || die "checkout of version $baseversion failed" &> /dev/null

    # Apply quilt patch stack

    # Try to run quiltimport
    git quiltimport --patches ${dir} --author 'Unknown Author <unknown@author.com>' &> /dev/null

    if [ $? -eq 0 ]; then
      echo "${baseversion} <- ${rtversion}" >> ../quiltimport-success
    else
      # THIS CASE IS ONLY FOR DEBUGGING. IN REAL LIFE EVERYTHING SHOULD SUCCEED!
      echo "${baseversion} <- ${rtversion}" >> ../quiltimport-fail
      # Undo all changes already made by quiltimport
      git reset --hard
      git clean -d -f -x
      git rebase --abort
      git reset --hard v${baseversion}
      
      # Manually apply all patches using quilt
      export QUILT_PATCHES=${dir}
      echo "manually applying Patch stack ${rtversion} on ${baseversion}"
      quilt push -a &> /dev/null || die "quilt push failed for ${rtversion}"
      unset QUILT_PATCHES
      git add -A &> /dev/null || die "git add failed"
      git commit -a -s -m "Yeah, Patches Applied." &> /dev/null || die "git commit failed"
      # delete quilt stack
      rm -rf .pc
    fi
  done
  cd ..
fi
