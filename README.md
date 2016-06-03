PaStA - Patch Stack Analysis
============================

Cloning
-------
```
$ git clone git@gitlab.lfd.sturhax.de:PaStA/PaStA.git
```

**PaStA** runs on *Python3*.
Dependencies:
- git
- pygit2
- git-python (for PaStA-resources only)
- termcolor
- R

TL;DR
-----

Run `./pasta -h`

Running PaStA
-------------

### Preparing PaStA PaStA configuration files and source code repositories of
projects are stored in a separate repository `PaStA-resources`

Running
```
$ ./pasta-prepare
```
will initialize and clone PaStA-resources (all preconfigured projects for
analysation) as git submodules. Inside PaStA-resources, the project code
repositories are submodules as well.

### Detecting and grouping similar patches
Analysing patches on the stacks and eventually linking them into equivalence
classes is split in two different command: `pasta analyse` and `pasta rate`.
Reason for the split is the comparatively long duration of the analysation
phase. After `pasta analyse`, you might want to reuse the results of the
analysation and run `pasta rate` for several times on the same data set.

The detection phase is split in five steps:
1. Initialisation of similar patches on the patch stacks
   ```
   $ ./pasta analyse init
   ```
2. Comparing successive versions on the patch stacks
   ```
   $ ./pasta analyse stack-succ
   $ ./pasta rate
   ```
3. For more fine-granular classification, compare representants of existing
   equivalence classes
   ```
   $ ./pasta analyse stack-rep
   $ ./pasta rate
   ```
4. Once you think you have found all equivalence classes you can find to find
   representants of them upstream
   ```
   $ ./pasta analyse upstream
   $ ./pasta rate
   ```
5. Finally, merge the results of the equivalence classes of the stacks and their
   corresponding upstream candidates by running
   ```
   $ ./pasta analyse finish
   ```

This will create a `patch-groups` file inside the resources directory of your
projecta. Each line represents a group of similar patches, commit hashes are
separated by whitespaces. A line can optionally end with ' => ' and point to an
upstream commit hash, if this group is connected to an upstream commit hash.

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

#### pasta-prepare
Initialises git submodules

Creating a new PaStA project
----------------------------
### Preparing the repository
All project-relevant file are located in `PaStA-resources/PROJECT_NAME/`.
Default locations inside that directory:
- `PROJECT_NAME.cfg`: the main configuration file of the project. This file sets
  the project name, different version ranges and default thresholds.
- `repo/`: This is the default location of the repository of the project
- `resources/patch-stack-definition.dat`: Definition of the patch stacks.
  Lines beginning with **#** are interpreted as comments, lines beginning with
  **##** group major versions of projects. Take a look at existing patch stack
  definitions.

### Rolling out history and identifying the commit hashes on patch stacks
For performance reasons, **PaStA** stores the diffs of all commit hashes as
single files. `diffs/` is the location of the patches of the project. After
creating the patch stack definition configuration file and the project
configuration file, add your project to the `PaStA-resources/prepare_projects`
script. Invoking this script will create the patch stack commit hash list inside
`PaStA-resources/PROJECT_NAME/resources/stack-hashes/` and roll out the git
history of the project.

### PaStA configuration format
The **PaStA** configuration file scheme is similar to the Windows *ini* format.
All configuration file inherit from `PaStA-resources/common/default.cfg` and
must implement some mandatory values. This is a minimal example for a project
configuration file:
```
[PaStA]
PROJECT_NAME = foobar

UPSTREAM_MIN = v1.0
UPSTREAM_MAX = v2.0
```

### Set active configuration
For setting the current active project **PaStA**, just create a symbolic link of
the configuration file to the root directory of **PaStA**. E.g.:
```
$ ln -sf PaStA-resources/PreemptRT/PreemptRT.cfg ./config
```

All further calls on **PaStA** tools will use this configuration file.
