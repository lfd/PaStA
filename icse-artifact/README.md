ICSE Artifact Evaluation
========================

## Introduction

To track the pre-integration history of software changes, our tool maps emails
containing patches to commits in a repository. The submitted artefacts allow
evaluators, among other things, to compute such mappings, and to determine a
set of optimal values for tuneable parameters that maximise the mapping
quality, as quantified by comparing the mapping for each parameter combination
against a given ground truth.

Our tool has been developed as an Open Source project on GitHub (GPLv2). We
follow strong developmental quality standards: the development history
comprises only well-documented (i.e., comprehensive commit messages) and
orthogonal (i.e., every revision is functional) changes. Industrial (such as
the Linux Foundation) as well as academic partners actively use and work with
our tool, which underlines functionality and reusability.

Evaluators familiar with basic command line interaction can evaluate our
artefacts on Linux or Mac OS X. We provide a docker container that can be
downloaded from our [institutions' website][1], or be built from scratch. This
makes the artefact evaluation process convenient, yet guarantees full
replicability from scratch.

### Artifact Overview

This is the list of artefacts that is required for the analysis:
 * [PaStA's code repository][2]
 * [Linux Kernel mailing list dump of May 2012][3]
 * [Ground Truth][4]

For convenience, these artefacts are bundled in a [prepared docker image][1].

### Installation and Analysis

Please find more details in [INSTALL.md][5] that accompanies our artefact
distribution. Note that there is **no** need to manually download any of the
artefacts as _everything_ is automised in scripts.

## Description

In our paper, we determine the optimum parameter set for our algorithm by
comparing a variety of parameter combinations against a manually created ground
truth. This consumes a lot of computational power and memory. A full
reproduction is possible, but required several weeks of computational efforts
on a 48 core system with 300GiB of RAM. So we do not suggest to perform a full
reproduction run ([scripts][6] are nonetheless available).

Our evaluation scripts use the optimal parameter set to determine the quality
of tool-reconstructed pre-integration history against the ground truth (as
quantified by the Fowlkes-Mallows score) to show the high accuracy of the
classification method presented in the paper.

## STATUS

We apply for the badges **reusable**, **available**, and **replicated**. Please
find the rationale in [STATUS][7].

## License

The [LICENSE][8] file can be found in the root directory of the project's
repository. The code and all results are published under the terms and
conditions of the GPLv2.

[1]: https://cdn.lfdr.de/PaStA/docker-pasta-icse.tar.gz
[2]: https://github.com/lfd/PaStA
[3]: https://cdn.lfdr.de/PaStA/LKML-2012-05.mbox
[4]: https://github.com/lfd/PaStA-resources/blob/master/linux/resources/2012-05-mbox-result.groundtruth
[5]: INSTALL.md
[6]: https://github.com/lfd/PaStA/blob/master/tools/all_analyses.sh
[7]: STATUS.md
[8]: https://github.com/lfd/PaStA/blob/master/COPYING
