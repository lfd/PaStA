#!/bin/bash

# get ML
#rm $1
#nntp-pull --server=news.gmane.org -v --reget $1

cat gmane.linux.rt.user | \
	grep -i -Pzo "^Subject: \[Announce.*\-rt.*\nDate:.*" -A1 | \
	sed -e 's/^Date: //' | \
	sed -e 's/Subject: \[.*\] //' > sum

cat sum | awk 'NR % 2 == 1' > versions
cat sum | awk 'NR % 2 == 0' | xargs -n 1 -I Z date --date="Z" +"%s \"%F %R\"" > dates

paste versions dates | sort -V > releaseDateList

rm dates sum versions
