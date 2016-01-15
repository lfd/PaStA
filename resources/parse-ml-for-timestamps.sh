#!/bin/bash

# get ML
#rm $1
#nntp-pull --server=news.gmane.org -v --reget $1

#grep -i -Pzo "^Subject: \[Announce.*\-rt.*\nDate:.*" -A1 | \

cat $1 | \
	grep -i -Pzo "^Subject: .*\-rt.*\nDate:.*" -A1 | \
	sed -e 's/^Date: //' | \
	sed -e 's/Subject: \[.*\] //' > sum

cat sum | awk 'NR % 2 == 1' > versions
cat sum | awk 'NR % 2 == 0' | xargs -n 1 -I Z date --date="Z" +"\"%F\"" > dates

paste versions dates > ${1}.releaseDateList

rm dates sum versions
