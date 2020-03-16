PaStA - Patch Stack Analysis
============================

Getting PaStA
-------------

Clone PaStA and its resources submodule. The resources contain configuration as
well as results of some sample projects.

```
$ git clone https://github.com/lfd/PaStA.git
$ cd PaStA
$ git submodule update --recursive --init resources
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
- flask
  - flask-wtf
  - flask-bootstrap
  - flask-nav

Please refer to this [Dockerfile](/docker/pasta-skeleton.dockerfile) to 
download the required dependencies.

Getting started
---------------
- Select the active project configuration
  `./pasta select linux`
- Run PaStA `./pasta -h`

Running PaStA
-------------

### PaStA's caches
Many projects contain thousands of commits. It is time-consuming to determine
and load commits. To increase overall performance, PaStA persists lists of
commit hashes and creates pkl-based commit caches. Those lists will be created
when needed. PaStA detects changes in the configuration file and automatically
updates those lists.

The commit cache has to be created manually:
```
$ ./pasta sync # Creates cache file for commits on the patch stacks
$ ./pasta sync -mbox # Update / synchronise mailboxes before creating caches
```

### Detecting and grouping similar patches
Detecting similar patches on patch stacks (i.e., branches) and eventually
linking them into equivalence classes is split in two different commands:
`pasta analyse` and `pasta rate`.
Reason for the split is the comparatively long duration of the analysation
phase. After `pasta analyse`, you might want to reuse the results of the
analysation and run `pasta rate` for several times on the same data set.

The detection phase is split in four steps:
1. Comparing successive versions on the patch stacks
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
projecta. Each line represents a group of similar patches, commit hashes are
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
Use the `select` command to set the active configuration. E.g.:
```
$ ./pasta select linux
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

1. `./pasta select linux`
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
