#!/usr/bin/env python
from __future__ import division, print_function
from builtins import map, filter, range
from past.utils import old_div

import math
import argparse
import ast
import collections
import json
import logging
import opentuner
import os
import random
import re
import shutil
import subprocess
import sys

from opentuner.resultsdb.models import Result, TuningRun
from opentuner.search import manipulator
from opentuner import tuningrunmain

FLAGS_WORKING_CACHE_FILE = 'cc_flags.json'
PARAMS_DEFAULTS_CACHE_FILE = 'cc_param_defaults.json'
PARAMS_WORKING_CACHE_FILE = 'cc_params.json'

log = logging.getLogger('gccflags')

argparser = argparse.ArgumentParser(parents=opentuner.argparsers())
# source should be a json file
argparser.add_argument('source', help='source file to compile')
argparser.add_argument('--run-dir', default='{}'.format(os.getcwd() + '/../'), help='A workspace that includes the to-be-compiled files (e.g. /path/to/OPS/apps/c/CloverLeaf)')
# A template should include a -I include_path, -L linked path
# -fPIC -Wall -ffloat-store -g -std=c++11 -fopenmp -Dgnu -DOPS_LAZY -lops_seq
# -I.. -I~/OPS-INSTALL/ops/c/include 
# -L~/OPS-INSTALL/ops/c/lib/gnu
argparser.add_argument('--basic', default='', help='a preset basic flags for compiling')
argparser.add_argument('--saved-name', default=None, help='Saved configuration name')
argparser.add_argument('--include', default='', help='include paths')
argparser.add_argument('--linking', default='', help='linking paths')
argparser.add_argument('--compile-template', default='/usr/bin/mpicxx {source} \
        {basic} {include} {linking} -o {output} -lpthread {flags}', \
        help='command to compile {source} into {output} with {flags}')
argparser.add_argument('--compile-limit', type=float, default=30,
                       help='kill compiler if it runs more than {default} sec')
argparser.add_argument('--scaler', type=int, default=4,
                       help='by what factor to try increasing parameters')
argparser.add_argument('--cc', default='/usr/bin/mpicxx', help='compiler to use')
argparser.add_argument('--early-time', type=float, default=0.00001, help="An early stop control time")
argparser.add_argument('--output', default='./tmp.bin',
                       help='temporary file for compiler to write to')
argparser.add_argument('--debug', action='store_true',
                       help='on compiler errors try to find the minimal set of args to reproduce error')
argparser.add_argument('--force-killall', action='store_true',
                       help='killall compiler processes before each collection')
argparser.add_argument('--memory-limit', default=1024 ** 3, type=int,
                       help='memory limit for child process')
argparser.add_argument('--no-cached-flags', action='store_true',
                       help='regenerate the lists of legal flags each time')
argparser.add_argument('--flags-histogram', action='store_true',
                       help='print out a histogram of flags')
argparser.add_argument('--flag-importance',
                       help='Test the importance of different flags from a given JSON file.')

def read_json_file(args):
    temp_out = []
    if args.saved_name is None:
        args.saved_name = args.source[:-14] + "_final_config.json"
    with open(args.source, 'r') as file:
        data = json.load(file)
    for temp in data['linking_files']:
        temp_out.append(args.run_dir + temp)
    linking_files = ' '.join(temp_out)
    temp_out = []
    for temp in data['basic_params']:
        temp_out.append(temp)
    basic_files = ' '.join(temp_out)
    temp_out = []
    for temp in data['include_path']:
        # temp_out.append('-I' + temp)
        temp_out.append(temp)
    include_paths = ' '.join(temp_out)
    temp_out = []
    for temp in data['linking_path']:
        # temp_out.append('-L' + temp)
        temp_out.append(temp)
    linking_paths = ' '.join(temp_out)
    return linking_files, basic_files, include_paths, linking_paths

class CloverLeafFlagsTuner(opentuner.measurement.MeasurementInterface):
    def __init__(self, *pargs, **kwargs):
        super(CloverLeafFlagsTuner, self).__init__(program_name=args.source, *pargs, **kwargs)
        self.gcc_version = self.extract_gcc_version()
        self.cc_flags = self.extract_working_flags()
        self.cc_param_defaults = self.extract_param_defaults()
        self.cc_params = self.extract_working_params()
        # No need to hardcode the cc_bugs here, just to be consistent with the tutorial
        self.cc_bugs = (['-time'])
        self.result_list = {}
        self.parallel_compile = True
        try:
            os.stat('./tmp')
        except OSError:
            os.mkdir('./tmp')
        self.run_baselines()
    
    def run_baselines(self):
        log.info("baseline perfs -O0=%.4f -O1=%.4f -O2=%.4f -O3=%.4f",
                 *[self.run_with_flags(['-O%d' % i], None).time
                   for i in range(4)])

    def extract_gcc_version(self):
        m = re.search(r'([0-9]+)[.]([0-9]+)[.]([0-9]+)', subprocess.check_output([self.args.cc, '--version']).decode('utf-8'))
        if m:
            gcc_version = tuple(map(int, m.group(1, 2, 3)))
        else:
            gcc_version = None
        log.debug('gcc version %s', gcc_version)
        return gcc_version

    def extract_working_flags(self):
        if os.path.isfile(FLAGS_WORKING_CACHE_FILE) and not args.no_cached_flags:
            found_cc_flags = json.load(open(FLAGS_WORKING_CACHE_FILE))
        else:
            optimizers, err = subprocess.Popen([self.args.cc, '--help=optimizers'],
                                               stdout=subprocess.PIPE).communicate()
            found_cc_flags = re.findall(r'^  (-f[a-z0-9-]+) ', optimizers.decode('utf-8'), re.MULTILINE)
            log.info('Determining which of %s possible compiler flags work', len(found_cc_flags))
            found_cc_flags = list(filter(self.check_if_flag_works, found_cc_flags))
            json.dump(found_cc_flags, open(FLAGS_WORKING_CACHE_FILE, 'w'))
        return found_cc_flags

    def extract_param_defaults(self):
        if os.path.isfile(PARAMS_DEFAULTS_CACHE_FILE) and not args.no_cached_flags:
            param_defaults = json.load(open(PARAMS_DEFAULTS_CACHE_FILE))
        else:
            print("Do not support the non cached values")
            param_defaults = None
        return param_defaults

    def extract_working_params(self):
        params, err = subprocess.Popen([self.args.cc, '--help=params'], stdout=subprocess.PIPE).communicate()
        params = str(params)
        all_params = re.findall(r'^  ([a-z0-9-]+) ', params, re.MULTILINE)
        all_params = sorted(set(all_params) & set(self.cc_param_defaults.keys()))
        if os.path.isfile(PARAMS_WORKING_CACHE_FILE) and not args.no_cached_flags:
            return json.load(open(PARAMS_WORKING_CACHE_FILE))
        else:
            log.info('Determining which of %s possible compiler params work', len(all_params))
            working_params = []
            for param in all_params:
                if self.check_if_flag_works('--param={}={}'.format(param, self.cc_param_defaults[param]['default'])):
                    working_params.append(param)
            json.dump(working_params, open(PARAMS_WORKING_CACHE_FILE, 'w'))
            return working_params

    def check_if_flag_works(self, flag, try_inverted=True):
        # Read in the flags here, a json file perhaps
        cmd = args.compile_template.format(source=args.source,
                basic=args.basic, include=args.inlcude, linking=args.linking,
                output=args.output, flags=flag, cc=args.cc)
        compile_result = self.call_program(cmd, limit=args.compile_limit)
        if compile_result['returncode'] != 0:
            log.warning("removing flag %s because it results in compile error", flag)
            return False
        if 'warning: this target' in compile_result['stderr'].decode("utf-8"):
            log.warning("removing flag {} because not supported by target".format(flag))
            return False
        if 'has been renamed' in compile_result['stderr'].decode("utf-8"):
            log.warning("removing flag {} because renamed".format(flag))
            return False
        if try_inverted and flag[:2] == '-f':
            if not self.check_if_flag_works(invert_gcc_flag(flag), try_inverted=False):
                log.warning("Odd... {} works but {} does not".format(flag, invert_gcc_flag(flag)))
                return False
        return True

    def manipulator(self):
        m = manipulator.ConfigurationManipulator()
        m.add_parameter(manipulator.IntegerParameter('-O', 0, 3))
        for flag in self.cc_flags:
            m.add_parameter(manipulator.EnumParameter(flag, ['on', 'off', 'default']))
        for param in self.cc_params:
            defaults = self.cc_param_defaults[param]
            if defaults['max'] <= defaults['min']:
                defaults['max'] = float('inf')
            defaults['max'] = min(defaults['max'], max(1, defaults['default']) * args.scaler)
            defaults['min'] = max(defaults['min'], old_div(max(1, defaults['default']), args.scaler))

            if param == 'l1-cache-line-size':
                m.add_parameter(manipulator.PowerOfTwoParameter(param, 4, 256))
            elif defaults['max'] > 128:
                m.add_parameter(manipulator.LogIntegerParameter(param, defaults['min'], defaults['max']))
            else:
                m.add_parameter(manipulator.IntegerParameter(param, defaults['min'], defaults['max']))

        return m

    def cfg_to_flags(self, cfg):
        flags = ['-O%d' % cfg['-O']]
        for flag in self.cc_flags:
            if cfg[flag] == 'on':
                flags.append(flag)
            elif cfg[flag] == 'off':
                flags.append(invert_gcc_flag(flag))

        for param in self.cc_params:
            flags.append('--param=%s=%d' % (param, cfg[param]))

        for bugset in self.cc_bugs:
            if len(set(bugset) & set(flags)) == len(bugset):
                flags.remove(bugset[-1])
        return flags

    def make_command(self, cfg):
        return args.compile_template.format(source=args.source, 
                basic=args.basic, include=args.inlcude, linking=args.linking,
                output=args.output, flags=' '.join(self.cfg_to_flags(cfg)), cc=args.cc)

    def get_tmpdir(self, result_id):
        return './tmp/%d' % result_id

    def cleanup(self, result_id):
        tmp_dir = self.get_tmpdir(result_id)
        shutil.rmtree(tmp_dir)

    def compile_and_run(self, desired_result, input, limit):
        cfg = desired_result.configuration.data
        compile_result = self.compile(cfg, 0)
        return self.run_precompiled(desired_result, input, limit, compile_result, 0)

    compile_results = {'ok': 0, 'timeout': 1, 'error': 2}

    def run_precompiled(self, desired_result, input, limit, compile_result, result_id):
        if self.args.force_killall:
            os.system('killall -9 cc1plus 2>/dev/null')
        if compile_result == self.compile_results['timeout']:
            return Result(state='TIMEOUT', time=float('inf'))
        elif compile_result == self.compile_results['error']:
            return Result(state='ERROR', time=float('inf'))

        tmp_dir = self.get_tmpdir(result_id)
        output_dir = '%s/%s' % (tmp_dir, args.output)
        try:
            run_result = self.call_program([output_dir], limit=limit, memory_limit=args.memory_limit)
        except OSError:
            return Result(state='ERROR', time=float('inf'))

        if run_result['returncode'] != 0:
            if run_result['timeout']:
                return Result(state='TIMEOUT', time=float('inf'))
            else:
                log.error('program error')
                return Result(state='ERROR', time=float('inf'))
        if run_result['time'] < args.early_time:
            self.manipulator().save_to_file(desired_result.configuration.data, "earlystop_{}_full.json".format(self.args.saved_name[:-18]))
            raise tuningrunmain.CleanStop("Early Stop")

        return Result(time=run_result['time'])

    def debug_gcc_error(self, flags):
        def fails(subflags):
            cmd = args.compile_template.format(source=args.source, 
                basic=args.basic, include=args.inlcude, linking=args.linking,
                output=args.output, flags=' '.join(subflags), cc=args.cc)
            
            compile_result = self.call_program(cmd, limit=args.compile_limit)
            return compile_result['returncode'] != 0

        if self.args.debug:
            while len(flags) > 8:
                log.error("compile error with %d flags, diagnosing...", len(flags))
                tmpflags = [x for x in flags if random.choice((True, False))]
                if fails(tmpflags):
                    flags = tmpflags

            minimal_flags = []
            for i in range(len(flags)):
                tmpflags = minimal_flags + flags[i + 1:]
                if not fails(tmpflags):
                    minimal_flags.append(flags[i])
            log.error("compiler crashes/hangs with flags: %s", minimal_flags)

    def compile(self, config_data, result_id):
        flags = self.cfg_to_flags(config_data)
        return self.compile_with_flags(flags, result_id)

    def compile_with_flags(self, flags, result_id):
        tmp_dir = self.get_tmpdir(result_id)
        try:
            os.stat(tmp_dir)
        except OSError:
            os.mkdir(tmp_dir)
        output_dir = '%s/%s' % (tmp_dir, args.output)
        cmd = args.compile_template.format(source=args.source, 
                basic=args.basic, include=args.inlcude, linking=args.linking,
                output=output_dir, flags=' '.join(flags), cc=args.cc)

        compile_result = self.call_program(cmd, limit=args.compile_limit, memory_limit=args.memory_limit)
        if compile_result['returncode'] != 0:
            if compile_result['timeout']:
                log.warning("compiler timeout")
                return self.compile_results['timeout']
            else:
                log.warning("compiler error %s", compile_result['stderr'])
                self.debug_gcc_error(flags)
                return self.compile_results['error']
        return self.compile_results['ok']

    def run_with_flags(self, flags, limit):
        return self.run_precompiled(None, None, limit, self.compile_with_flags(flags, 0), 0)

    def save_final_config(self, configuration):
        print("Best flags written to {}".format(self.args.saved_name))
        self.manipulator().save_to_file(configuration.data, '{}'.format(self.args.saved_name))

    def flags_histogram(self, session):
        counter = collections.Counter()
        q = session.query(TuningRun).filter_by(state='COMPLETE')
        total = q.count()
        for tr in q:
            print(tr.program.name)
            for flag in self.cfg_to_flags(tr.final_config.data):
                counter[flag] += old_div(1.0, total)
        print(counter.most_common(20))

    def flag_importance(self):
        with open(self.args.flag_importance) as fd:
            best_cfg = json.load(fd)
        flags = self.cfg_to_flags(best_cfg)
        counter = collections.Counter()
        baseline_time = self.flags_mean_time(flags)
        for flag in flags[1:]:
            delta_flags = [f for f in flags if f != flag]
            flag_time = self.flags_mean_time(delta_flags)
            impact = max(0.0, flag_time - baseline_time)
            if math.isinf(impact):
                impact = 0.0
            counter[flag] = impact
            print(flag, '{:.4f}'.format(impact))
        total_impact = sum(counter.values())
        remaining_impact = total_impact
        print(r'\bf Flag & \bf Importance \\\hline')
        for flag, impact in counter.most_common(20):
            print(r'{} & {:.1f}\% \\\hline'.format(flag, 100.0 * impact / total_impact))
            remaining_impact -= impact
        print(r'{} other flags & {:.1f}% \\\hline'.format(len(flags) - 20, 100.0 * remaining_impact / total_impact))

    def flags_mean_time(self, flags, trials=10):
        precompiled = self.compile_with_flags(flags, 0)
        total = 0.0
        for _ in range(trials):
            total += self.run_precompiled(None, None, None, precompiled, 0).time
        return old_div(total, trials)

    def prefix_hook(self, session):
        if self.args.flags_histogram:
            self.flags_histogram(session)
            sys.exit(0)
        if self.args.flag_importance:
            self.flag_importance()
            sys.exit(0)

def invert_gcc_flag(flag):
    assert flag[:2] == '-f'
    if flag[2:5] != 'no-':
        return '-fno-' + flag[2:]
    return '-f' + flag[5:]



if __name__ == '__main__':
    opentuner.init_logging()
    args = argparser.parse_args()
    args.source, args.basic, args.inlcude, args.linking = read_json_file(args)
    CloverLeafFlagsTuner.main(args)

