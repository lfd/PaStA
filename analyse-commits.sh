#!/bin/bash

source common.sh

require git
require realpath

#rm -rf subjects
#mkdir subjects
SUBJECTS=$(realpath subjects)
cd $KERNELDST

branches=$(git branch --list | cut -b 3- | grep analysis | sort -V)

for i in $branches
do

continue
  rtversion=$(echo $i | sed 's/analysis\-\(.*\)/\1/')
  baseversion=$(echo $rtversion | sed 's/\(.*\)\-rt.*/\1/')
  
  # special treatment for 3.12.0 and 3.14-0
  # ... There's absolutely no version nomenclature consistency in PreemptRT...
  if [ "$baseversion" = "3.12.0" ] || [ "$baseversion" = "3.14.0" ]; then
    baseversion=$(sed -e 's/\.0$//' <<< $baseversion)
  fi
  
  echo "Working on $rtversion..."
  
  git --no-pager log --pretty=format:"%s" v${baseversion}...${i} | sort > \
    ${SUBJECTS}/${rtversion}
done

# Get overall number of commits
noc="number_of_commits"
cat > $noc <<EOL
# Absolute number of commits of the RT Patch
# Increasing number    Number of commits    Version String
EOL

cd ..

cntr=1
ver="1.00"

declare -a xticsArray

for i in $(ls ${SUBJECTS}/* | sort -V)
do
    rtversion=$(basename $i)
	commits=$(wc -l $i | sed -e 's/\(.*\) .*/\1/')

    if [[ $rtversion =~ ${ver}.* ]]
	then
	    label=0
	else
	    label=1
		ver=$(echo $rtversion | sed -e 's/^\([0-9]*\.[0-9]*\).*/\1/')
		xticsArray+=("\"${rtversion}\" ${cntr}")
	fi

    echo "$cntr $commits \"${rtversion}\"" >> $noc
    cntr=$((cntr + 1))
done

xtics=${xticsArray[0]}
for i in `seq 1 $((${#xticsArray[@]}-1))`
do
	xtics="${xticsArray[$i]}, $xtics"
done

cat > number_of_commits.plot <<EOL
set title 'PreemptRT: Number of commits'
set terminal postscript eps enhanced color font 'Helvetica,10'
set output 'preemptrt_commitcount.eps'

unset xtics
set ylabel "Number of commits"
set xlabel "PreemptRT kernel version"
set xtics nomirror rotate by -45
set xtics (${xtics})
plot "number_of_commits" u 1:2 w points notitle
EOL

gnuplot number_of_commits.plot
