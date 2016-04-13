PaStA - Patch Stack Analysis
============================

Cloning
-------
```
$ git clone git@gitlab.lfd.sturhax.de:PaStA/PaStA.git
```

**PaStA** runs on *Python3*.
Dependencies:
- git-python
- termcolor

Running PaStA
-------------

### Preparing PaStA PaStA configuration files and source code repositories of
projects are stored in a separate repository `PaStA-resources`

Running
```
$ ./prepare_pasta
```
will initialize and clone PaStA-resources (all preconfigured projects for
analysation) as git submodules. Inside PaStA-resources, the project code
repositories are submodules as well.

### Detecting and grouping similar patches
Analysing patches on the stacks and eventually linking them into equivalence
classes is split in two different command: `analyse` and `interactive-rating`.
Reason for the split is the comparatively long duration of the analysation
phase. After one analysation phase, you might want to reuse the results of the
analysation and run `interactive-rating` for several times on the same data set.

The detection phase is split in five steps:
1. Initialisation of similar patches on the patch stacks
   ```
   $ ./analyse -mode init
   ```
2. Comparing successive versions on the patch stacks
   ```
   $ ./analyse -mode stack-succ
   $ ./interactive-rating
   ```
3. For more fine-granular classification, compare representants of existing
   equivalence classes
   ```
   $ ./analyse -mode stack-rep
   $ ./interactive-rating
   ```
4. Once you think you have found all equivalence classes you can find to find
   representants of them upstream
   ```
   $ ./analyse -mode upstream
   $ ./interactive-rating
   ```
5. Finally, merge the results of the equivalence classes of the stacks and their
   corresponding upstream candidates by running
   ```
   $ ./analyse -mode finish
   ```

By default, this will create a `patch-groups` file inside the resources of your
project.

### Run some statistics
After **PaStA** created the `patch-groups` file, you can run some predefined
statistics on your data by running

```
./run_statistics
```

This will automatically create a new directory inside your resources and place
some *csv* files that are suitable for **R** input.  Afterwards,
`run-statistics` will automatically invoke R, plot some graphs and store the
plots in the same directory as *png* and *tikz* files taht can be used for
*LaTeX* input.

If you want **PaStA** only to create the *csv* files without running **R**, you
can invoke it by using `./run-statistics -noR -R /tmp/foo/`.  This will not
invoke **R** and place the *csv*s in `/tmp/foo`.

PaStA commands in detail
------------------------
### Main Components
To see a list of available options, run main components with `-h`.

### Tools
#### compare-patches
`compare-patches` evaluates a list of commit hashes and displays the evaluation
result as well as the original commits.

#### prepare_pasta
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
  **##** group major versions of projects. Have a look at existing patch stack
  definitions.

### Rolling out history and identifying the commit hashes on patch stacks
For reasons of performance, **PaStA** rolls out the complete git history.
`log/` is the default location of the history of the project.
After creating the patch stack definition configuration file and the project
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
