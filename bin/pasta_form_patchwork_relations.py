"""
PaStA - Patch Stack Analysis

Author:
  Rohit Sarkar <rohitsarkar5398@gmail.com>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import sys

from logging import getLogger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

log = getLogger(__name__[-15:])


def form_patchwork_relations(config, argv):
    parser = argparse.ArgumentParser(prog='form_patchwork_relations',
                                     description='Form patch groups using Patchwork IDs instead of Message IDs')
    parser.add_argument('-infile', metavar='infile', default=config.f_clustering,
                        help='The patch groups file to be used as input. '
                             'If not specified will default to value of PATCH_GROUPS config variable')
    parser.add_argument('-outfile', metavar='outfile',
                        default=os.path.join(config.project_root, 'resources', 'patch-groups-patchwork'),
                        help='Name of the output file')

    args = parser.parse_args(argv)

    if config.mode != config.Mode.MBOX:
        log.error('Only works in Mbox mode!')
        return -1

    config.repo.register_mbox(config)
    mbox = config.repo.mbox

    _, clustering = config.load_cluster(f_clustering=args.infile)
    clustering_patchwork = Clustering()

    for downstream, upstream in clustering.iter_split():
        patchwork_ids = set().union(*[mbox.get_patchwork_ids(p) for p in downstream])
        clustering_patchwork.insert(*patchwork_ids)

    clustering_patchwork.to_file(args.outfile)
