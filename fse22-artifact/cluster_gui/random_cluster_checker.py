#!/usr/bin/env python3
"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Authors:
   Pia Eichinger <pia.eichinger@hotmail.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""


from collections import defaultdict
from tkinter import *
from tkinter import font
from PIL import ImageTk, Image
import glob
import os
import sys


def parse_csv(filename, must_exist):
    retval = defaultdict(str)
    if not os.path.isfile(filename) and not must_exist:
        return retval

    with open(filename, 'r') as f:
        content = f.read().strip().split('\n')
    for line in content:
        filename, direction = [x.strip() for x in line.split(',')]
        retval[filename] = direction
    return retval


def check_cluster_marked(el):
    return len(guess_dict[el])


def select_cluster(event):
    selection = event.widget.curselection()
    if selection:
        index = selection[0]
        data = event.widget.get(index)

        global curr_cluster
        curr_cluster = data

        # Get the guess for the current cluster
        note = guess_dict[curr_cluster]
        e_check.delete(0, END)
        e_check.insert(0, note)

        path1 = os.path.join(d_cluster_img, "random_" + data)
        path2 = os.path.join(d_cluster_img, data)
        correct_side = solution_dict[curr_cluster]

        if correct_side == 'r':
            global image1
            global image2
            image1 = Image.open(path1)
            image2 = Image.open(path2)

            global photo1
            global photo2
            photo1 = ImageTk.PhotoImage(image1)
            photo2 = ImageTk.PhotoImage(image2)
        else:
            image1 = Image.open(path2) # paths are switched
            image2 = Image.open(path1)

            photo1 = ImageTk.PhotoImage(image1)
            photo2 = ImageTk.PhotoImage(image2)
            
        canvas1.itemconfig(image_container1, image=photo1)
        canvas2.itemconfig(image_container2, image=photo2)


def mark_cluster():
    mark = e_check.get()
    guess_dict[curr_cluster] = mark.strip()
    with open(output_file, 'w') as f:
        for key, value in guess_dict.items():
            f.write('%s, %s\n' % (key, value.strip()))

    lb.itemconfigure(lb.curselection(), fg="green" if check_cluster_marked(curr_cluster) else "black")


def zoom1(factor):
    global photo1
    global image1
    new_size = (int(image1.size[0] * factor), int(image1.size[1] * factor))

    image1 = image1.resize(new_size, Image.ANTIALIAS)
    photo1 = ImageTk.PhotoImage(image1)
    canvas1.itemconfigure(image_container1, image=photo1)  # update image


def zoom2(factor):
    global photo2
    global image2
    new_size = (int(image2.size[0] * factor), int(image2.size[1] * factor))
    image2 = image2.resize(new_size, Image.ANTIALIAS)
    photo2 = ImageTk.PhotoImage(image2)
    canvas2.itemconfigure(image_container2, image=photo2)  # update image


d_cluster_img = sys.argv[1]
output_file = os.path.join(d_cluster_img, "guess.csv")
solution_file = os.path.join(d_cluster_img, "solution.csv")

random_clusters = glob.glob(os.path.join(d_cluster_img, 'random_*.png'))
clusters = glob.glob(os.path.join(d_cluster_img, 'cluster_*.png'))
curr_cluster = ""

solution_dict = parse_csv(solution_file, must_exist=True)
guess_dict = parse_csv(output_file, must_exist=False)

root = Tk()
root.title("Random Cluster Checker -- %s" % (os.path.basename(d_cluster_img)))

root.grid_rowconfigure(2, weight=7)
root.grid_columnconfigure((0), weight=7)
root.grid_columnconfigure((4), weight=5)

# ROW 0
msg = Message(root, text="Left cluster is real: l\n"
                         "Right cluster is real: r\n"
                         "No guess: ?\n", font=(None, 9), width=250)
msg.grid(row=0, column=3, padx=13, pady=5, sticky=N+W, columnspan=2)

ffs = font.Font(family='Courier', size=10)

lb = Listbox(root, width=30, bd=1, selectmode='single', font=ffs, exportselection=False)
lb.grid(row=0, column=2, padx=5, pady=5, sticky=W+E+S, columnspan=1, rowspan=2)
lb.bind('<<ListboxSelect>>', select_cluster)

# populate the clusters
for f in clusters:
    lb.insert(END, os.path.basename(f))
    lb.itemconfig(END, fg="green" if check_cluster_marked(os.path.basename(f)) else "black")

yscroll0 = Scrollbar(command=lb.yview, orient=VERTICAL)
yscroll0.grid(row=0, column=3, sticky=N+S+W, rowspan=2)
lb.configure(yscrollcommand=yscroll0.set)

e_check = Entry(root, width=35, bd=1, )
e_check.grid(row=0, column=4, padx=5, sticky=W+E+S)

# ROW 1
b1 = Button(root, text="Mark", command=mark_cluster)
b1.grid(row=1, column=4, padx=5, sticky=N+W)

canvas1 = Canvas(root)

# take the first one as default
image1 = Image.open(clusters[0])
photo1 = ImageTk.PhotoImage(image1)
image_container1 = canvas1.create_image((0, 0), anchor=NW, image=photo1)

canvas1.bind('<ButtonPress-1>', lambda event: canvas1.scan_mark(event.x, event.y))
canvas1.bind("<B1-Motion>", lambda event: canvas1.scan_dragto(event.x, event.y, gain=1))

canvas1.grid(row=2, column=0, sticky=N+S+W+E, columnspan=1)

Button(root, text='+', command=lambda: zoom1(1.1)).grid(row=3, column=0, sticky='nwe')
Button(root, text='-', command=lambda: zoom1(0.9)).grid(row=4, column=0, sticky='nwe')

canvas2 = Canvas(root)

image2 = Image.open(random_clusters[0])
photo2 = ImageTk.PhotoImage(image2)
image_container2 = canvas2.create_image(0, 0, anchor=NW, image=photo2)

canvas2.bind('<ButtonPress-1>', lambda event: canvas2.scan_mark(event.x, event.y))
canvas2.bind("<B1-Motion>", lambda event: canvas2.scan_dragto(event.x, event.y, gain=1))
canvas2.grid(row=2, column=2, sticky=N+S+W+E, columnspan=3)

Button(root, text='+', command=lambda: zoom2(1.1)).grid(row=3, column=2, columnspan=3, sticky='nwe')
Button(root, text='-', command=lambda: zoom2(0.9)).grid(row=4, column=2, columnspan=3, sticky='nwe')

mainloop()
