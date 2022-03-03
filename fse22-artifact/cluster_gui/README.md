Compare Real-World Clusters against Random Clusters
===================================================

Usage
-----
Simply run the dispatcher:
$ ./do\_repro.sh

The dispatcher will start the reproduction for each project (Linux, U-Boot,
QEMU, Xen). In the text field, enter your guess which cluster is the REAL one
(i.e., 'l' or 'r'). If you are uncertain, enter '?'. You can skip clusters. The
green text color indicates that the cluster has already been marked. You can
edit your choice at any time.

After finishing, please zip the directory and send it back to:

    pia.eichinger@st.oth-regensburg.de

Requirements
------------

Please install python3 and Tkinter.
