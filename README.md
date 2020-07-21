PaStA - Patch Stack Analysis
============================

About
-----

**PaStA**  is a tool for detecting similar patches. In PaStA, a patch is
everything that can be split up to a commit message and a diff. Patches can
either come from patch stacks or mailboxes. A patch stack is a fork/branch (a
set of commits) from a git project that are developed and maintained
independently of the base project.  . Patch stacks are, for example, used by
extensions of the Linux kernel (e.g., the Preempt-RT patch stack), or custom
vendor trees.  Many OSS projects, like the Linux kernel, use a mail-based
workflow. PaStA is able to assign mails from mailboxes to commits in
repositories. It comes with heuristics that are able to detect patches even if
their content significantly changes over time. In this way, PaStA is able to
track different revisions of a patch.


**PaStA** is a research project from the Technical University of Applied
Sciences Regensburg. The following papers describe the methodology, use-cases
and accuracy of PaStA:

- [Observing Custom Software Modifications: A Quantitative Approach of Tracking the Evolution of Patch Stacks](https://arxiv.org/abs/1607.00905)
- [The List is the Process: Reliable Pre-Integration Tracking of Commits on Mailing Lists](https://arxiv.org/pdf/1902.03147.pdf)

Presentation resources:

- This [LPC 2019 recording](https://www.youtube.com/watch?v=QG1YDQ1HOKE) and
  [Embedded Linux Conference Europe 2019 recording](https://www.youtube.com/watch?v=YCfU-2dXDq0)
  present core ideas behind the project. Slides:
  [here](https://static.sched.com/hosted_files/osseu19/5c/pasta-elce19.pdf)
- The whole presentation is summarised in [this](https://lwn.net/Articles/804511/) article.

Getting PaStA
-------------

Clone **PaStA** and its resources submodule. The resources contain
project-specific configuration, project-related repositories and public inboxes
as well as results of **PaStA**'s analysis for some sample projects.

```
$ git clone https://github.com/lfd/PaStA.git
$ cd PaStA
$ ./tools/update_resources.sh # This might take some time to complete
```

Requirements
------------

**PaStA** requires *Python3* and comes with the following dependencies:
- git
- pygit2
- git-python (for patch_descriptions only)
- R (tikzDevice, ggplot2)
- fuzzywuzzy + python-levenshtein
- procmail
- python-anytree
- python-dateparser
- python scikit-learn
- python-toml
- python-tqdm
- python-requests
- flask
  - flask-wtf
  - flask-bootstrap
  - flask-nav

Please refer to this [Dockerfile](/docker/pasta-skeleton.dockerfile) to
download the required dependencies.

Getting started
---------------
- Select the active project configuration
  `./pasta set_config linux`
- Run PaStA `./pasta -h`

Running PaStA
-------------
### Modes
**PaStA** has two modes of operation, mailbox (mbox) mode and patch stack mode:

#### Mailbox Mode
The development of a number of open source projects is carried out on public
mailing lists. A prime example of this is the Linux kernel. Developers send
patches to mailing lists, where they are reviewed by other subscribers or
maintainers. Note that a project may use several mailing lists. The Linux
kernel, for example, uses more than 200 different lists for its subsystems.
Discussion related to new features, bug reports etc. also takes place on the
mailing list.

Given a mailbox of such a mailing list, PaStA searches for all mails that
contain patches. PaStA understands regular patch emails, as they are formatted
by 'git format-patch', or patches that are sent as an attachment. PaStA tries
to repair emails with best effort (e.g., erroneous encoding, non-conform
headers, …). PaStA also maps these patches to their corresponding upstream
commits.

PaStA understands several mailbox exchange formats:
- Raw mboxes
- Public inboxes (Given a link to the mailbox)
- Messages from [Patchwork](https://github.com/getpatchwork/patchwork)

#### Patch stack mode
This mode uses patch stack definition files to compare succesive versions of
patch stacks. Different patch stacks are defined in the patch stack definition.
An example configuration, as well as script can be found in the resources of
the PreemptRT project.


### Initialise PaStA's caches
Many projects contain thousands of commits. It is time-consuming to determine
and load commits. To increase overall performance, PaStA persists lists of
commit hashes and creates pkl-based commit caches. Those lists will be created
when needed. PaStA detects changes in the configuration file and automatically
updates those lists.

The commit cache has to be created manually:
```
$ ./pasta sync # Creates cache file for commits on the patch stacks
$ ./pasta sync -mbox # Update / synchronise mailboxes before creating caches if in mail box mode
```

### Detecting and grouping similar patches
Detecting similar patches on patch stacks (i.e. branches) or mail boxes and eventually
linking them into equivalence classes is split in two different commands:
`pasta analyse` and `pasta rate`.
Reason for the split is the comparatively long duration of the analysation
phase. After `pasta analyse`, you might want to reuse the results of the
analysation and run `pasta rate` for several times on the same data set.

The detection phase is split in three steps:
1. In patch stack mode, the comparison of successive versions on the patch stack:
   ```
   $ ./pasta analyse succ
   $ ./pasta rate
   ```
2. For more fine-granular classification, compare representants of existing
   equivalence classes
   ```
   $ ./pasta analyse rep
   $ ./pasta rate
   ```
3. Once you think you have found all equivalence classes you can find to find
   representants of them upstream
   ```
   $ ./pasta analyse upstream
   $ ./pasta rate
   ```

This will create a `patch-groups` file inside the resources directory of your
project. Each line represents a group of similar patches, commit hashes are
separated by whitespaces. A line can optionally end with ' => ' and point to
upstream commit hash(es).

### Run statistics
After **PaStA** created the `patch-groups` file, you can run some predefined
statistics on your data by running

```
$ ./pasta statistics
```

This will automatically create a new directory inside your resources and place
*csv* files that serve as input for **R**.  Afterwards, `pasta statistics`
automatically invokes **R**, plots some graphs and stores them in the same
directory as *png* and *tikz* files.

If you want **PaStA** only to create the *csv* files only without running
**R**, you can invoke it by using `./pasta statistics -noR -R /tmp/foo/`. This
will not invoke **R** and place the *csv*s in `/tmp/foo`.

PaStA commands in detail
------------------------
### PaStA subcommands
To get list of all available PaStA commands, run `./pasta -h`. `pasta sub -h`
gives you further detailed information about subcommands.

### Tools
#### pasta compare
`./pasta compare` analyses a list of commit hashes given as command line
arguments and displays the evaluation result as well as the original commits.

Creating a new PaStA project
----------------------------
### Preparing the repository
All project-relevant file are located in `resources/PROJECT_NAME/`.
Default locations inside that directory:
- `config`: the main configuration file of the project. This file sets the
  project name, different version ranges, time windows and default thresholds.
- `repo/`: This is the default location of the repository of the project. While
  not strictly required, repos are usually added as git submodules.
- `resources/patch-stack-definition.dat`: Definition of the patch stacks.
  Lines beginning with **#** are interpreted as comments, lines beginning with
  **##** group major versions of projects. Take a look at existing patch stack
  definitions.

### PaStA configuration format
The **PaStA** configuration file scheme is similar to the Windows *ini* format.
All configuration file inherit from `resources/common/default.cfg` and
must implement some mandatory values. This is a minimal example for a project
configuration file:
```
[PaStA]
PROJECT_NAME = foobar
MODE = mbox / patchstack

UPSTREAM = v1.0..v2.0
```

### Set active configuration
Use the `set_config` command to set the active configuration. E.g.:
```
$ ./pasta set_config linux
```

All further calls on **PaStA** tools will use this configuration file. To use a
specific configuration for a single **PaStA** command, this may be overridden
with the `-c` command line parameter:
```
$ ./pasta -c busybox subcommand ...
```

PaStA Mailbox Analysis
----------------------

**PaStA** is able to map mails from mailboxes (e.g. dumps of mailing lists or
[public inboxes][1]) to commit hashes of repositories. PaStA searches for mails
in the mailbox that contain patches. Yet, PaStA does not entirely understand
all different mail formats. After all potential patches have been detected,
PaStA will save those patches in a commit cache file. This file can be used for
further analysis and is compared against all 'upstream' commits (master
branch).

1. `./pasta set_config linux`
2. Either get mailboxes. PaStA supports raw unix-style mailboxes and public
   inboxes, and add them to the configuration. Use the linux project
   configuration as a reference. There are several possibilities to acquire
   mailbox data:
   * Use [nntp2mbox][2] on gmane.org
   * Convert your local maildir
   * Use public inboxes from [git.kernel.org][3]
3. Parse mailboxes and create local caches with `./pasta sync -mbox`

To compare all mails on the list against each other:

4. Run `./pasta analyse rep`
5. Run `./pasta rate`

To compare all mails on the list against upstream:

6. Run `./pasta analyse upstream`
7. Run `./pasta rate`
8. Your result will be stored in `resources/[project]/resources/similar-mailbox`

[1]: https://public-inbox.org/README.html
[2]: https://github.com/xai/nntp2mbox
[3]: https://git.kernel.org/pub/scm/public-inbox/

PaStA and Patchwork
--------------------
The results of PaStA's analyses can be used by [Patchwork](http://jk.ozlabs.org/projects/patchwork/).

## Setting up PaStA and Patchwork
Assuming a working setup of PaStA already exists, here are the steps necessary for Patchwork integration

1. Install Patchwork on your system, following the guidelines in Patchwork's [documentation](https://patchwork.readthedocs.io/en/latest/development/installation/)

2. Start a shell inside Patchwork's docker container with `docker-compose run --rm web --shell`

3. Bring up a Patchwork development server, by running
`./manage.py runserver 0.0.0.0:8000` inside the shell started in step 2. You should now have a Patchwork instance
running at `<Patchwork-Docker-Container-IP-address>:8000` on your host. The Patchwork container's IP address can be
found using `ifconfig` command on Linux distributions.

4. Start PaStA's docker container on the same network as the Patchwork one by running the command:
`docker run -it --rm --network patchwork_default --name pasta -v </path/to/PaStA>:/home/pasta pasta:latest`

5. Set the Patchwork specific settings in config:
```
[mbox]
...

[mbox.patchwork]
url = 'http://<Patchwork-Container-IP-Address>/api/1.2/'
projects = [{ id = x, initial_archive="path/to/archive", list_email="list@domain.org"},
{id = y, initial_archive="", list_email="anotherlist@anotherdomain.org"}, ...]
page_size = 10

# Provide an api_token token or username/password if restricted api access is
# needed (e.g updating relations)
token = 'your_token'
username = 'your_username'
password = 'your_password'
```

Each Patchwork project from which mails are to be imported needs to be listed in the configuration. If
the `initial_archive` property of the project is specified (project with id `x` in the example above)
, PaStA will import mails from the archive treating it as a raw mail box. If the `initial_archive`
property is an empty string (project with id `y` in the example above),
PaStA will fetch mails using Patchwork's API, only importing those mails which are not already in PaStA.
