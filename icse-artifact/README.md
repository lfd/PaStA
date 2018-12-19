ICSE Artifact Evaluation
========================

## Introduction

Our work, and the results in the paper in particular, can be fully reproduced
in a docker container. The base image of the container can either be manually
built for a fully reproducible environment setup, or downloaded as a prepared
container.

### Artifact Overview

This is the list of artifacts that is required for the analysis:
 * [PaStA's code repository][1]
 * [Linux Kernel mailing list dump of May 2012][2]
 * [Optional: Prepared docker image][3]

### Installation and Analysis

Note that there is **no** need for manual download of artifacts as _everything_
is automised in scripts. Please follow the guidelines in [INSTALL][4].

## Description

In our paper, we try to find an optimum parameter set for our algorithm.
Therefore, we compare a variety of combinations of parameters against a
manually created ground truth. This process consumes a lot of computational
power and memory. Though not impossibly, this is clearly not suitable for
reproducability for obvious reasons. Hence, we limit the analysis on the
optimum parameter set that we found during our analysis. This show the high
accuary of our approach.

Inside the docker container, a script will run the analysis and report the
Fowlkes-Mallows score as presented in our paper.

## STATUS

We apply for the badge **replicated**. Please find the rationale in [STATUS][6].

## License

The [LICENSE][5] file can be found in the root directory of the project's
repository. The code and all results are published under the terms and
conditions of the GPLv2.

[1]: https://github.com/lfd/PaStA
[2]: https://cdn.lfdr.de/PaStA/LKML-2012-05.mbox
[3]: https://cdn.lfdr.de/PaStA/docker-pasta-icse.tar.gz
[4]: INSTALL.md
[5]: https://github.com/lfd/PaStA/blob/master/COPYING
[6]: STATUS.md
