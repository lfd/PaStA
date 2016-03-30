PaStA - Patch Stack Analysis
============================

Cloning
-------
```
$ git clone git@gitlab.lfd.sturhax.de:PaStA/PaStA.git
```

Preparing PaStA
---------------

PaStA configuration files and source code repositories of projects are stored in a separate repository 'PaStA-resources'

Running
```
$ ./prepare_pasta
```
will initialize and clone PaStA-resources as a git submodule. Inside PaStA-resources, the project code repositories are submodules as well.
