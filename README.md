## Mini-tuner for OPS benchmarking

Notes: now only support tiled files, haven't evaluated the others yet.
The tuning examples mostly refer to [opentuner-gccflages](https://github.com/jansel/opentuner/tree/567c48bc3cc66a178fc5462ecc58dd48670bbbf9/examples/gccflags)

## Prerequest

- Install Opentuner (see: [OpenTuner](https://github.com/jansel/opentuner/tree/567c48bc3cc66a178fc5462ecc58dd48670bbbf9) Installation part)
- Install OPS from source (see: [OP-DSL](https://github.com/OP-DSL/OPS))

We expect your directory tree will be something like:

```shell
. # (Your workspace)
├──OPS-INSTALL
├──OPS 
│   ├──apps 
│   │   ├──fortran
│   │   ├──c 
│   │   │  ├──access 
│   │   │  ├──...# (other top directories for OPS running examples)
```

This `ops-mini-tuner` should be put right under the `/workspace/OPS/apps/c` (should be fine if you want it to lie somewhere else). We also offer a python script for those machines that do not have `jq` installed. So far, the script may still have some issues:

- We only deal with one relative path at the moment, e.g. flags like `-I.` or `-L.`. For others like `-I..` are not well handled. Double check the paths if the tunning goes wrong.
- The `kernel_files` in `*.json` is a hack for the time being. A customized function should be offered in the future to handle multi-kernels compiling cases. 

## How to run

Try `./script.sh help` for the script usage advice.

```shell
# Clean all the opentuner tmp files
./script.sh clean 

# Clean all the *.in *.out and *.json files, if you are running the full tuning for the first time, try to do that first, 
# it gives you a clean environment and also allows opentuner to test each of the working compiling flags
./script.sh cleanall

# Run with each example
./script.sh [<if_running_minitune>] [<make_name>] [<Makefile_path>] [<compiling_command>]

# Example 1, running a mini tunning demo for cloverleaf_tiled [default]
./script.sh 1 cloverleaf_tiled ../CloverLeaf/ /usr/bin/mpicxx

# Example 2, running full tunning for cloverleaf_tiled 
./script.sh 0 cloverleaf_tiled ../CloverLeaf/ /usr/bin/mpicxx
```


`<example_name>_minimal.py` is coded in a fixed path, which means you might encounter errors while running the mini tunning demo, try changing the hyperparameters if needed.
