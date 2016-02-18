#!/usr/bin/env gnuplot

reset

# Din A4 Output
set size ratio 0.71 # din a ratio
set terminal postscript enhanced landscape color font "Arial," 9
set output 'commits.ps'

# zum drucken:
# ps2ps -sPAGESIZE=a4 commits.ps commits_a4.ps

set title 'PreemptRT: Number of commits'
set ylabel 'Number of commits'
set xlabel 'Timeline'

set style data lines

set xdata time
set timefmt '%Y-%m-%d'
set format x '%Y-%m-%d'
set xrange ['2007-06-01' : '2016-03-01']

unset xtics
set xtics nomirror rotate by -45
set xtics 0,0,0

set xtics add ('2007-07-12')
set xtics add ('2007-07-24')
set xtics add ('2007-11-15')
set xtics add ('2008-05-17')
set xtics add ('2008-07-29')
set xtics add ('2009-02-11')
set xtics add ('2011-07-20')
set xtics add ('2011-11-18')
set xtics add ('2012-04-10')
set xtics add ('2012-10-09')
set xtics add ('2013-03-22')
set xtics add ('2013-08-01')
set xtics add ('2013-11-10')
set xtics add ('2014-04-11')
set xtics add ('2015-02-16')
set xtics add ('2015-05-19')
set xtics add ('2015-07-14')
set xtics add ('2015-12-23')
#set label '2.6.22.1-rt2'	at '2007-07-12', 374 offset -4, -1
#set label '2.6.23-rc1-rt0'	at '2007-07-24', 326 offset -4, -1
#set label '2.6.24-rc2-rt1'	at '2007-11-15', 370 offset -4, -1
#set label '2.6.25.4-rt1'	at '2008-05-17', 350 offset -4, -1
#set label '2.6.26-rt1'		at '2008-07-29', 402 offset -4, -1
#set label '2.6.29-rc4-rt1'	at '2009-02-11', 212 offset -4, -1
#set label '3.0-rc7-rt0'		at '2011-07-20', 224 offset -4, -1
#set label '3.2-rc2-rt3'		at '2011-11-18', 240 offset -4, -1
#set label '3.4-rc2-rt1'		at '2012-04-10', 242 offset -4, -1
#set label '3.6.1-rt1'		at '2012-10-09', 250 offset -4, -1
#set label '3.8.4-rt1'		at '2013-03-22', 282 offset -4, -1
#set label '3.10.4-rt1'		at '2013-08-01', 275 offset -4, -1
#set label '3.12.0-rt1'		at '2013-11-10', 277 offset -4, -1
#set label '3.14.0-rt1'		at '2014-04-11', 309 offset -4, -1
#set label '3.18.7-rt1'		at '2015-02-16', 309 offset -4, -1
#set label '4.0.4-rt1'		at '2015-05-19', 343 offset -4, -1
#set label '4.1.2-rt1'		at '2015-07-14', 266 offset -4, -1
#set label '4.4-rc6-rt1'		at '2015-12-23', 256 offset -4, -1

plot "commitcount-2.6.22-rt"	every ::1 using 2:5 linetype 1 linecolor 1 title '2.6.22-rt', \
	 "commitcount-2.6.23-rt"	every ::1 using 2:5 linetype 1 linecolor 2 title '2.6.23-rt', \
	 "commitcount-2.6.24-rt"	every ::1 using 2:5 linetype 1 linecolor 3 title '2.6.24-rt', \
	 "commitcount-2.6.25-rt"	every ::1 using 2:5 linetype 1 linecolor 4 title '2.6.25-rt', \
	 "commitcount-2.6.26-rt"	every ::1 using 2:5 linetype 1 linecolor 5 title '2.6.26-rt', \
	 "commitcount-2.6.29-rt"	every ::1 using 2:5 linetype 1 linecolor 7 title '2.6.29-rt', \
	 "commitcount-3.0-rt"		every ::1 using 2:5 linetype 1 linecolor 8 title '3.0-rt', \
	 "commitcount-3.2-rt"		every ::1 using 2:5 linetype 1 linecolor 9 title '3.2-rt', \
	 "commitcount-3.4-rt"		every ::1 using 2:5 linetype 1 linecolor 10 title '3.4-rt', \
	 "commitcount-3.6-rt"		every ::1 using 2:5 linetype 1 linecolor 11 title '3.6-rt', \
	 "commitcount-3.8-rt"		every ::1 using 2:5 linetype 1 linecolor 12 title '3.8-rt', \
	 "commitcount-3.10-rt"		every ::1 using 2:5 linetype 1 linecolor 13 title '3.10-rt', \
	 "commitcount-3.12-rt"		every ::1 using 2:5 linetype 1 linecolor 14 title '3.12-rt', \
	 "commitcount-3.14-rt"		every ::1 using 2:5 linetype 1 linecolor 16 title '3.14-rt', \
	 "commitcount-3.18-rt"		every ::1 using 2:5 linetype 1 linecolor 17 title '3.18-rt', \
	 "commitcount-4.0-rt"		every ::1 using 2:5 linetype 1 linecolor 18 title '4.0-rt', \
	 "commitcount-4.1-rt"		every ::1 using 2:5 linetype 1 linecolor 19 title '4.1-rt', \
	 "commitcount-4.4-rt"		every ::1 using 2:5 linetype 1 linecolor 20 title '4.4-rt'
