#!/usr/bin/env python

""" PC-BASIC test script

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import shutil
import filecmp
import contextlib
import traceback
import time
import json
from copy import copy, deepcopy
from contextlib import contextmanager


# make pcbasic package accessible
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [os.path.join(HERE, '..')] + sys.path

import pcbasic


# copy of pythonpath for use by testing cycle
PYTHONPATH = copy(sys.path)
# test timing file
TEST_TIMES = os.path.join(HERE, '_settings', 'slowtest.json')
# umber of slowest tests to show or exclude
SLOWSHOW = 20

# ANSI colours for test status
STATUS_COLOURS = {
    'exception': '01;37;41',
    'passed': '00;32',
    'accepted': '00;36',
    'failed (old)': '00;33',
    'failed': '01;31',
}

def is_same(file1, file2):
    try:
        return filecmp.cmp(file1, file2, shallow=False)
    except EnvironmentError:
        return False

@contextlib.contextmanager
def suppress_stdio(do_suppress):
    # flush last outbut before muffling
    sys.stderr.flush()
    sys.stdout.flush()
    if not do_suppress:
        yield
    else:
        with pcbasic.compat.muffle(sys.stdout):
            with pcbasic.compat.muffle(sys.stderr):
                yield

def contained(arglist, elem):
    try:
        arglist.remove(elem)
    except ValueError:
        return False
    return True


def parse_args():
    args = sys.argv[1:]
    loud = contained(args, '--loud')
    reraise = contained(args, '--reraise')
    fast = contained(args, '--fast')
    all = not args or contained(args, '--all')
    cover = contained(args, '--coverage')
    return args, all, fast, loud, reraise, cover


class TestFrame(object):

    def __init__(self, dirname, reraise):
        self._dirname = dirname
        self._reraise = reraise

    @contextmanager
    def check_output(self):
        self._output_dir = os.path.join(self._dirname, 'output')
        self._model_dir = os.path.join(self._dirname, 'model')
        self._known_dir = os.path.join(self._dirname, 'known')
        self.old_fail = False
        if os.path.isdir(self._output_dir):
            self.old_fail = True
            shutil.rmtree(self._output_dir)
        os.mkdir(self._output_dir)
        for filename in os.listdir(self._dirname):
            if os.path.isfile(os.path.join(self._dirname, filename)):
                shutil.copy(
                    os.path.join(self._dirname, filename),
                    os.path.join(self._output_dir, filename)
                )
        self._top = os.getcwd()
        os.chdir(self._output_dir)
        yield self
        self.passed = True
        self.known = True
        self.failfiles = []
        for path, dirs, files in os.walk(self._model_dir):
            for f in files:
                if f.endswith('.pyc'):
                    continue
                filename = os.path.join(path[len(self._model_dir)+1:], f)
                if (
                        not is_same(
                            os.path.join(self._output_dir, filename),
                            os.path.join(self._model_dir, filename)
                        )
                        and not os.path.isfile(os.path.join(self._dirname, filename))
                    ):
                    self.failfiles.append(filename)
                    self.known = (
                        os.path.isdir(self._known_dir) and
                        is_same(
                            os.path.join(self._output_dir, filename),
                            os.path.join(self._known_dir, filename)
                        )
                    )
                    self.passed = False
        for path, dirs, files in os.walk(self._output_dir):
            for f in files:
                if f.endswith('.pyc'):
                    continue
                filename = os.path.join(path[len(self._output_dir)+1:], f)
                if (
                        not os.path.isfile(os.path.join(self._model_dir, filename))
                        and not os.path.isfile(os.path.join(self._dirname, filename))
                    ):
                    self.failfiles.append(filename)
                    self.passed = False
                    self.known = False
        os.chdir(self._top)
        if self.passed:
            shutil.rmtree(self._output_dir)

    @contextmanager
    def check_crash(self):
        self.crash = None
        try:
            yield self
        except Exception as e:
            self.crash = e
            if self._reraise:
                raise

    @contextmanager
    def guard(self):
        with self.check_output():
            with self.check_crash():
                yield self

    @property
    def status(self):
        if self.crash:
            return 'exception'
        if self.passed:
            return 'passed'
        if self.known:
            return 'accepted'
        if self.old_fail:
            return 'failed (old)'
        return 'failed'


class Timer(object):

    @contextmanager
    def time(self):
        start_time = time.time()
        start_cpu = time.clock()
        yield self
        self.wall_time = time.time() - start_time
        self.cpu_time = time.clock() - start_cpu


class Coverage(object):

    def __init__(self, cover):
        self._on = cover

    @contextmanager
    def track(self):
        if self._on:
            import coverage
            cov = coverage.coverage()
            cov.start()
            yield self
            cov.stop()
            cov.save()
            cov.html_report()
        else:
            yield


def testname(cat, name):
    return '/'.join((cat, name))



def run_tests(args, all, fast, loud, reraise, cover):
    if all:
        args = [
            os.path.join('basic', _preset, _test)
            for _preset in os.listdir(os.path.join(HERE, 'basic'))
            for _test in sorted(os.listdir(os.path.join(HERE, 'basic', _preset)))
        ]
    skip = {}
    if fast:
        try:
            with open(TEST_TIMES) as timefile:
                times = dict(json.load(timefile))
        except EnvironmentError:
            pass
        else:
            # exclude slowest tests
            skip = dict(sorted(times.items(), key=lambda _p: _p[1], reverse=True)[:SLOWSHOW])
    times = {}
    results = {}
    with Coverage(cover).track() as coverage:
        with Timer().time() as overall_timer:
            # preserve environment
            startdir = os.path.abspath(os.getcwd())
            save_env = deepcopy(os.environ)
            # run all tests
            for name in args:
                # reset testing environment
                os.chdir(startdir)
                os.environ = deepcopy(save_env)
                # normalise test name
                if name.endswith('/'):
                    name = name[:-1]
                _, name = name.split(os.sep, 1)
                # e.g. basic/gwbasic/TestName
                try:
                    _dir, name = os.path.split(name)
                    _, category = os.path.split(_dir)
                except ValueError:
                    category = 'gwbasic'
                dirname = os.path.join(HERE, 'basic', category, name)
                print(
                    '\033[00;37mRunning test %s/\033[01m%s \033[00;37m.. ' % (category, name),
                    end=''
                )
                if testname(category, name) in skip:
                    print('\033[00;30mskipped.\033[00;37m')
                    continue
                if not os.path.isdir(dirname):
                    print('\033[01;31mno such test.\033[00;37m')
                    continue
                with suppress_stdio(not loud):
                    with Timer().time() as timer:
                        with TestFrame(dirname, reraise).guard() as test_frame:
                            # we need to include the output dir in the PYTHONPATH
                            # for it to find extension modules
                            sys.path = PYTHONPATH + [os.path.abspath('.')]
                            # run PC-BASIC
                            pcbasic.run('--interface=none')
                times[testname(category, name)] = timer.wall_time
                results[testname(category, name)] = test_frame.status
                print('\033[%sm%s.\033[00;37m' % (
                    STATUS_COLOURS[test_frame.status], test_frame.status
                ))
                if test_frame.crash:
                    print('    %r' % test_frame.crash)
    # update stored times
    if all and not fast:
        with open(TEST_TIMES, 'w') as timefile:
            json.dump(times, timefile)
    return results, times, overall_timer

def report_results(results, times, overall_timer):
    res_stat = {
        _status: [_test for _test, _teststatus in results.items() if _teststatus == _status]
        for _status in set(results.values())
    }
    print()
    print(
        '\033[00mRan %d tests in %.2fs (wall) %.2fs (cpu):' %
        (len(results), overall_timer.wall_time, overall_timer.cpu_time)
    )
    for status, tests in res_stat.items():
        print('    %d %s' % (len(tests), status), end='')
        if status == 'passed':
            print('.')
        else:
            print(': \033[%sm%s.\033[00;37m' % (
                STATUS_COLOURS[status], ' '.join(tests)
            ))
    # update slow-tests file
    slowtests = sorted(times.items(), key=lambda _p: _p[1], reverse=True)
    print()
    print('\033[00;37mSlowest tests:')
    print(
        '    '
        + '\n    '.join('{}: {:.1f}'.format(_k, _v) for _k, _v in slowtests[:SLOWSHOW])
    )



if __name__ == '__main__':
    args = parse_args()
    results = run_tests(*args)
    report_results(*results)
