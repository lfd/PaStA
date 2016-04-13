PaStA - Patch Stack Analysis
============================

Cloning
-------
```
$ git clone git@gitlab.lfd.sturhax.de:PaStA/PaStA.git
```

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
invoke **R** and place the *csv*s in `/tmp/foo`
