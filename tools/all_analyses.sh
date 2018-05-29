#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis
A tool for tracking the evolution of patch stacks

Copyright (c) OTH Regensburg, 2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.
"""

import numpy as np
import os
import pathlib
from queue import Queue
from multiprocessing import cpu_count
from threading import Thread
from time import sleep

pretend = False

if pretend:
	def call(foo):
		print(' '.join(foo))
else:
	from subprocess import call

path = './resources/linux/resources/'
evalresult = '%s%s' % (path, 'evaluation-result.pkl')
pg_template = './mbox-result-template'
ground_truth = '%s/%s' % (path, '2012-05-mbox-result.groundtruth')

def zarange(start, stop, step):
	return np.append(np.arange(start, stop, step), 0)

workers_rate = int(cpu_count())
workers_compare = int(cpu_count())

range_tf = np.arange(1.0, 0.59, -0.05)
range_th = np.arange(1.0, 0.1, -0.05)
range_ta = np.arange(1.0, 0.59, -0.01)
range_dlr = zarange(1.0, 0, -0.1)
range_w = zarange(1.0, 0, -0.1)

print('range_tf: %s' % range_tf)
print('range_th: %s' % range_th)
print('range_ta: %s' % range_ta)
print('range_w: %s' % range_w)
print('range_dlr: %s' % range_dlr)
print('num results: %u' % (len(range_tf) * len(range_th) * len(range_ta) *
			   len(range_dlr) * len(range_w)))
quit()

def queue_fill(queue):
	i = 0
	for tf in range_tf:
		for th in range_th:
			for ta in range_ta:
				for dlr in range_dlr:
					for w in range_w:
						queue.put((tf, th, ta, dlr, w))
						i = i + 1
						# if i == 20000:
						# 	return i
	return i

def pg_filename(tf, th, ta, dlr, w):
	res_path = path + 'RES/tf-%0.3f/th-%0.3f/ta-%0.3f/dlr-%0.3f/' % (tf, th, ta, dlr)
	return res_path, 'w-%0.3f' % w

def er_filename(tf, th, upstream):
	if upstream:
		upstream = 'upstream-'
	else:
		upstream = ''

	return path + 'ER/evaluation-%sresult-%0.2f-%0.2f.pkl' % (upstream, tf, th)

def er_filename_lock(tf, th, upstream):
	return er_filename(tf, th, upstream) + '.lock'

def parallelise(maxsize, task):
	queue = Queue(maxsize=workers_rate)
	threads = []
	for i in range(maxsize):
		t = Thread(target=task, args=(queue,))
		t.start()
		threads.append(t)

	i = queue_fill(queue)
	print('put %d items' % i)

	queue.join()

	for i in range(maxsize):
		queue.put(None)
	for t in threads:
		t.join()

##### ANALYSIS PHASE BEGINS HERE ######
for upstream in [False, True]:
	for tf in range_tf:
		for th in range_th:

			destination = er_filename(tf, th, upstream)
			lock = er_filename_lock(tf, th, upstream)
			if os.path.isfile(destination):
				print('ER exists for tf %0.2f th %0.2f. Skipping...' % (tf, th))
				continue
			if os.path.isfile(lock):
				print('Lock exists for tf %0.2f th %0.2f. Skipping...' % (tf, th))
				continue

			call(['touch', lock])
			if upstream:
				mode = 'upstream'
			else:
				mode = 'rep'

			call(['./pasta', 'analyse', '-mbox', mode, '-tf', '%0.2f' % tf, '-th', '%0.2f' % th, '-er', destination])
			call(['rm', lock])

#### RATE PHASE BEGINS HERE ######
def worker_rate(q):
	while True:
		item = q.get()
		if item is None:
			break
		tf, th, ta, dlr, w = item

		print('Working on %0.3f %0.3f %0.3f %0.3f %0.3f' % item)
		result_dir, filename = pg_filename(tf, th, ta, dlr, w)
		result_destination = result_dir + filename
		result_destination_intermediate = result_destination + '.lock'

		if not os.path.isdir(result_dir):
			pathlib.Path(result_dir).mkdir(parents=True, exist_ok=True)

		if os.path.isfile(result_destination):
			print('Result %s exists. Skipping...' % result_destination)
			q.task_done()
			continue

		if os.path.isfile(result_destination_intermediate):
			print('Lock for result %s exists. Skipping...' % result_destination_intermediate)
			q.task_done()
			continue

		er_stack = er_filename(tf, th, False)
		er_upstream = er_filename(tf, th, True)

		if not os.path.isfile(er_stack) or not os.path.isfile(er_upstream):
			print('Stack or Upstream result not found. Skipping')
			q.task_done()
			continue

		thresholds = ['-ta', '%0.3f' % ta, '-dlr', '%0.3f' % dlr, '-w', '%0.3f' % w]
		err = call(['cp', '-av', pg_template, result_destination_intermediate])
		if err:
			q.task_done()
			continue
		err = call(['./pasta', 'rate', '-er', er_stack, '-pg', result_destination_intermediate] + thresholds)
		if err:
			print('error rating')
			q.task_done()
			continue
		err = call(['./pasta', 'rate', '-er', er_upstream, '-pg', result_destination_intermediate] + thresholds)
		if err:
			print('error rating upstream')
			q.task_done()
			continue
		err = call(['mv', result_destination_intermediate, result_destination])
		if err:
			print('error moving')
			q.task_done()
			continue

		q.task_done()

#parallelise(workers_rate, worker_rate)
#quit()

#### Compare_eqclasses phase begins here ####

def worker_compare(q):
	while True:
		item = q.get()
		if item is None:
			break
		tf, th, ta, dlr, w = item

		result_dir, filename = pg_filename(tf, th, ta, dlr, w)
		result_destination = result_dir + filename
		comp_destination = result_destination + '.comp'

		if os.path.isfile(comp_destination):
			print('%s already exists. Skipping...' % comp_destination)
			q.task_done()
			continue

		call(['./pasta', 'compare_eqclasses', '-ar', '-mi', '-nmi', '-pur', '-fm', '-f', comp_destination, ground_truth, result_destination])

		q.task_done()

parallelise(workers_compare, worker_compare)
