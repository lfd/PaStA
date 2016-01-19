set title 'PreemptRT: Number of commits'
#set terminal postscript eps enhanced color font 'Helvetica,10'
#set output 'preemptrt_commitcount.eps'
unset xtics
set ylabel 'Number of commits'
set xlabel 'PreemptRT kernel version'
set xtics nomirror rotate by -45

set xtics ("2.6.22.1-rt2" 1, "2.6.23-rc1-rt0" 8, "2.6.24-rc2-rt1" 36, "2.6.25.4-rt1" 69, "2.6.26-rt1" 76, "2.6.29-rc4-rt1" 92, "3.0-rc7-rt0" 126, "3.2-rc2-rt3" 225, "3.4-rc2-rt1" 320, "3.6.1-rt1" 407, "3.8.4-rt1" 438, "3.10.4-rt1" 454, "3.12.0-rt1" 509, "3.14.0-rt1" 559, "3.18.7-rt1" 590, "4.0.4-rt1" 608, "4.1.2-rt1" 614, "4.4-rc6-rt1" 626)
plot "./num_commits.dat" u 1:7 w points notitle
pause -1 'press key to exit'
