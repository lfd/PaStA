Installation and Setup
======================

To reproduce our results, we provide a prepared docker container. If desired,
the docker container can also be built from scratch, please find the
instructions in Section "Docker from scratch". These are the requirements for
the analysis:

  * A Linux distribution of your choice
  * Docker
  * curl, zcat, bash, git

1. Clone the repository

```
$ git clone https://github.com/lfd/PaStA.git
$ cd PaStA/docker
```

2. Run the analysis

```
$ ./run-icse-artifact.sh
```

Step 2 will automatically download a prepared container image, start the
container and run the analysis.

Docker from Scratch (expert)
============================

We also provide the dockerfiles to create the docker container from scratch.

1. Clone the repository

```
$ git clone https://github.com/lfd/PaStA.git
$ cd PaStA/docker
```

2. Create the docker container

The following command will first create a docker container for PaStA's base
system, inherit from that image and create a ICSE Artifact specific container
that contains all required artefact files and the correct version of our tool.

```
$ ./build-icse.sh
```

3. Start the container, and attach to it

```
$ docker run -ti pasta:icse-artifact
```

4. Run the analysis

Inside the container, run

```
$ ./icse-artifact-analysis.sh
```
