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

plot "commitcount-2.6.22.1"	using 5:6 linetype 1 linecolor 1 title '2.6.22-rt', \
	 "commitcount-2.6.23"	using 5:6 linetype 1 linecolor 2 title '2.6.23-rt', \
	 "commitcount-2.6.24" 	using 5:6 linetype 1 linecolor 3 title '2.6.24-rt', \
	 "commitcount-2.6.25.4" using 5:6 linetype 1 linecolor 4 title '2.6.25.4-rt', \
	 "commitcount-2.6.26" 	using 5:6 linetype 1 linecolor 5 title '2.6.26-rt', \
	 "commitcount-2.6.29"	using 5:6 linetype 1 linecolor 7 title '2.6.29-rt', \
	 "commitcount-3.0"		using 5:6 linetype 1 linecolor 8 title '3.0-rt', \
	 "commitcount-3.2"		using 5:6 linetype 1 linecolor 9 title '3.2-rt', \
	 "commitcount-3.4"		using 5:6 linetype 1 linecolor 10 title '3.4-rt', \
	 "commitcount-3.6.1"	using 5:6 linetype 1 linecolor 11 title '3.6.1-rt', \
	 "commitcount-3.8.4"	using 5:6 linetype 1 linecolor 12 title '3.8.4-rt', \
	 "commitcount-3.10.4"	using 5:6 linetype 1 linecolor 13 title '3.10.4-rt', \
	 "commitcount-3.12.0"	using 5:6 linetype 1 linecolor 14 title '3.12.0-rt', \
	 "commitcount-3.14.0"	using 5:6 linetype 1 linecolor 16 title '3.14.0-rt', \
	 "commitcount-3.18.7"	using 5:6 linetype 1 linecolor 17 title '3.18.7-rt', \
	 "commitcount-4.0.4"	using 5:6 linetype 1 linecolor 18 title '4.0.4-rt', \
	 "commitcount-4.1.2"	using 5:6 linetype 1 linecolor 19 title '4.1.2-rt', \
	 "commitcount-4.4"		using 5:6 linetype 1 linecolor 20 title '4.4-rt', \
