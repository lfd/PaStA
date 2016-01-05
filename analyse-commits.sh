#!/bin/bash

source common.sh

require git
require realpath

rm -rf subjects
mkdir subjects
SUBJECTS=$(realpath subjects)
cd $KERNELDST

branches=$(git branch --list | cut -b 3- | grep analysis | sort -V)

for i in $branches
do
  rtversion=$(echo $i | sed 's/analysis\-\(.*\)/\1/')
  baseversion=$(echo $rtversion | sed 's/\(.*\)\-rt.*/\1/')
  
  # special treatment for 3.12.0 and 3.14-0
  # ... There's absolutely no version nomenclature consistency in PreemptRT...
  if [ "$baseversion" = "3.12.0" ] || [ "$baseversion" = "3.14.0" ]; then
    baseversion=$(sed -e 's/\.0$//' <<< $baseversion)
  fi
  
  echo "Working on $rtversion..."
  
  git --no-pager log --pretty=format:"%s" v${baseversion}...${i} > \
    ${SUBJECTS}/${rtversion}
done
