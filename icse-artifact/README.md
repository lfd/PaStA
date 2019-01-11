ICSE Artifact Evaluation
========================

## Introduction

Our work, and the results in the paper in particular, can be fully reproduced
using a docker container. The base image of the container can be
 * manually built from scratch for a fully reproducible environment setup (substantial temporal effort)
 * downloaded as a [prepared container][3].

### Artifact Overview

This is the list of artifacts that is required for the analysis:
 * [PaStA's code repository][1]
 * [Linux Kernel mailing list dump of May 2012][2]
 * [Ground Truth][7]

For convenience, these artifacts are bundled in a [prepared docker image][3].

### Installation and Analysis

Note that there is **no** need to manually download any of the artifacts as
_everything_ is automised in scripts. Please follow the guidelines in
[INSTALL][4].

## Description

In our paper, we try to find an optimum parameter set for our algorithm.
Therefore, we compare a variety of combinations of parameters against a
manually created ground truth. This process consumes a lot of computational
power and memory. Reproducing the optimisation process is possible, but
required several weeks of computational efforts on a 48 core system with 300GiB
of RAM. So we do not suggest to perform a full reproduction run (scripts are
available in [...][...]).

Our evaluation scripts use the optimal parameter set to determine the quality
of tool-reconstructed pre-integration history against the ground truth to show
the high accuracy of the classification method presented in the paper.

Inside the docker container, a script will run the analysis and report the
Fowlkes-Mallows score as presented in our paper.

## STATUS

We apply for the badges **reusable**, **available**, and **replicated**. Please
find the rationale in [STATUS][6].

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
[7]: https://github.com/lfd/PaStA-resources/blob/c1ca8502f83539bacf2026bcc6b0109d477f8a23/linux/resources/2012-05-mbox-result.groundtruth
