## Mini-tunner for OPS benchmarking

Notes: now only support tiled files, haven't evaluted the others yet.
The tuning examples mostly refers to [opentuner-gccflages](https://github.com/jansel/opentuner/tree/567c48bc3cc66a178fc5462ecc58dd48670bbbf9/examples/gccflags)

## Prerequest

- Install opentuner (see: [OpenTuner](https://github.com/jansel/opentuner/tree/567c48bc3cc66a178fc5462ecc58dd48670bbbf9) Installation part)
- Install OPS from source (see: [OP-DSL](https://github.com/OP-DSL/OPS))

We expect your directory tree will be something like:

```shell
/workspace/OPS/
|-/workspace/OPS/apps/
|-/workspace/OPS/apps/c/
|-/workspace/OPS/apps/c/...(all the top directories for OPS running examples)

/workspace/OPS-INSTALL
```

This `ops-mini-tunner` should be put right under the `/workspace/OPS/apps/c` (should be fine if you want it to lie on somewhere else)

## How to run

Try `./script.sh help` for the script usage advice.

```shell
# Clean all the opentuner tmp files
./script.sh clean 

# Clean all the *.in *.out and *.json files, if you run are running the full tuning for the first time, try to do that first, 
# it gives you a clean environment and also allow opentuner to test each of working compiling flags
./script.sh cleanall

# Run with each examples
./script.sh [<if_running_minitune>] [<make_name>] [<Makefile_path>] [<compiling_command>]

# Example 1, running a mini tunning demo for cloverleaf_tiled [default]
./script.sh 1 cloverleaf_tiled ../CloverLeaf/ /usr/bin/mpicxx

# Example 2, running full tunning for cloverleaf_tiled 
./script.sh 0 cloverleaf_tiled ../CloverLeaf/ /usr/bin/mpicxx
```


`<example_name>_minimal.py` is coded in a fixed path, which means you might occur errors while running the mini tunning demo, try change the hyperparameters if needed.
