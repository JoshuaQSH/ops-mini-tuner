#!/usr/bin/env python
#
# Autotune flags to mpicxx to optimize the performance of laplaced2d (step 7)
#
# This is meant to be only for the tutorial, refer to opentuner gccflags_minimal.py
#

import opentuner
from opentuner import ConfigurationManipulator
from opentuner import EnumParameter
from opentuner import IntegerParameter
from opentuner import MeasurementInterface
from opentuner import Result
from opentuner import tuningrunmain

import argparse
import json

def read_json_file(file_name):
    with open(file_name, 'r') as file:
        data = json.load(file)
    return data

GCC_FLAGS = [
    'align-functions', 'align-jumps', 'align-labels',
    'align-loops', 'asynchronous-unwind-tables',
    'branch-count-reg', 'branch-probabilities',
    # ... (176 total)
]

# (name, min, max)
GCC_PARAMS = [
    ('early-inlining-insns', 0, 1000),
    ('gcse-cost-distance-ratio', 0, 100),
    ('iv-max-considered-uses', 0, 1000),
    # ... (145 total)
]

RUNFILES = "laplace2d_tiled_tunebase.json"
RUNFILES_PATH = "~/OPS/apps/c/laplace2d_tutorial/step7/"
SAVEFILES = "laplace2d_final_mini_config.json"
EARLY_STOP_TIME = 0.001


class MpicxxFlagsTuner(MeasurementInterface):
    
    def save_final_config(self, configuration):
        print("Optimal paramters saved to ", SAVEFILES)
        print("Best paramters: ", configuration.data)
        self.manipulator().save_to_file(configuration.data, SAVEFILES)
        
    def manipulator(self):
        """
        Define the search space by creating a
        ConfigurationManipulator
        """
        manipulator = ConfigurationManipulator()
        manipulator.add_parameter(
            IntegerParameter('opt_level', 0, 3))
        for flag in GCC_FLAGS:
            manipulator.add_parameter(
                EnumParameter(flag,
                              ['on', 'off', 'default']))
        for param, min, max in GCC_PARAMS:
            manipulator.add_parameter(
                IntegerParameter(param, min, max))
        return manipulator

    def compile(self, cfg, id):
        """
        Compile a given configuration in parallel
        """
        file_data = read_json_file(RUNFILES)
        temp_out = []
        for temp in file_data['linking_files']:
            temp_out.append(RUNFILES_PATH + temp)
        # linking_files = ' '.join(file_data['linking_files'])
        linking_files = ' '.join(temp_out)
        gcc_cmd = '{} -o ./tmp{}.bin'.format("/usr/bin/mpicxx", id)
        gcc_cmd += ' -O{0}'.format(cfg['opt_level'])
        gcc_cmd += ' -fPIC -Wall -ffloat-store -g -std=c++11 -fopenmp -Dgnu -DOPS_LAZY'
        gcc_cmd += ' -I~/OPS-INSTALL/ops/c/include -L~/OPS-INSTALL/ops/c/lib/gnu'
        gcc_cmd += ' {}'.format(linking_files)
        gcc_cmd += ' -I../laplace2d_tutorial/step7/ -lops_seq'
        for flag in GCC_FLAGS:
            if cfg[flag] == 'on':
                gcc_cmd += ' -f{0}'.format(flag)
            elif cfg[flag] == 'off':
                gcc_cmd += ' -fno-{0}'.format(flag)
        for param, min, max in GCC_PARAMS:
            gcc_cmd += ' --param {0}={1}'.format(
                param, cfg[param])
        return self.call_program(gcc_cmd)

    def run_precompiled(self, desired_result, input, limit, compile_result, id):
        """
        Run a compile_result from compile() sequentially and return the performance
        """
        assert compile_result['returncode'] == 0

        try:
            run_result = self.call_program('./tmp{0}.bin'.format(id))
            assert run_result['returncode'] == 0
            
            # Early stop - demo
            if run_result['time'] < EARLY_STOP_TIME:
                self.manipulator().save_to_file(desired_result.configuration.data,"earlystop_laplace2d.json")
                raise tuningrunmain.CleanStop("Early stop with {}, with: {}".format(run_result['time'],desired_result.configuration.data))
        finally:
            self.call_program('rm ./tmp{0}.bin'.format(id))

        return Result(time=run_result['time'])

    def compile_and_run(self, desired_result, input, limit):
        """
        Compile and run a given configuration then
        return performance
        """
        cfg = desired_result.configuration.data
        compile_result = self.compile(cfg, 0)
        return self.run_precompiled(desired_result, input, limit, compile_result, 0)


if __name__ == '__main__':
    argparser = opentuner.default_argparser()
    MpicxxFlagsTuner.main(argparser.parse_args())

