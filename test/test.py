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
SLOWTESTS = os.path.join(HERE, '_settings', 'slowtest.json')
# umber of slowest tests to show or exclude
SLOWSHOW = 20


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


class OutputChecker(object):

    def __init__(self, dirname):
        self._dirname = dirname

    def __enter__(self):
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
        return self

    def __exit__(self, one, two, three):
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


class CrashChecker(object):

    def __init__(self, reraise):
        self._reraise = reraise

    @contextmanager
    def guard(self):
        self.crash = None
        try:
            yield self
        except Exception as e:
            self.crash = e
            if self._reraise:
                raise

class Timer(object):

    @contextmanager
    def time(self):
        start_time = time.time()
        start_cpu = time.clock()
        yield self
        self.wall_time = time.time() - start_time
        self.cpu_time = time.clock() - start_cpu


def run_tests(args, all, fast, loud, reraise, cover):

    if all:
        args = [
            os.path.join('basic', _preset, _test)
            for _preset in os.listdir(os.path.join(HERE, 'basic'))
            for _test in sorted(os.listdir(os.path.join(HERE, 'basic', _preset)))
        ]

    if fast:
        try:
            with open(SLOWTESTS) as slowfile:
                slowtests = dict(json.load(slowfile))
        except EnvironmentError:
            pass
        else:
            # get slowest tests
            slowtests = sorted(slowtests.items(), key=lambda _p: _p[1], reverse=True)[:SLOWSHOW]
            # exclude
            slowtests = set(os.path.join('basic', _key) for _key, _ in slowtests)
            args = [_arg for _arg in args if _arg not in slowtests]

    if cover:
        import coverage
        cov = coverage.coverage()
        cov.start()
    else:
        cov = None

    numtests = 0
    failed = []
    knowfailed = []
    oldfailed = []
    crashed = []
    times = {}

    with Timer().time() as overall_timer:

        # preserve environment
        startdir = os.path.abspath(os.getcwd())
        save_env = deepcopy(os.environ)

        for name in args:
            # reset testing environment
            os.chdir(startdir)
            os.environ = deepcopy(save_env)

            TESTNAME = name

            if TESTNAME.endswith('/'):
                TESTNAME = TESTNAME[:-1]

            _, name = TESTNAME.split(os.sep, 1)

            # e.g. basic/gwbasic/TestName
            try:
                DIR, TESTNAME = os.path.split(TESTNAME)
                _, PRESET = os.path.split(DIR)
            except ValueError:
                PRESET = 'gwbasic'
            PATH = os.path.join(HERE, 'basic', PRESET, TESTNAME)
            print('\033[00;37mRunning test %s/\033[01m%s \033[00;37m.. ' % (PRESET, TESTNAME), end='')
            dirname = PATH
            if not os.path.isdir(dirname):
                print('\033[01;31mno such test.\033[00;37m')
                continue
            with OutputChecker(dirname) as output_checker:
                # we need to include the output dir in the PYTHONPATH for it to find extension modules
                sys.path = PYTHONPATH + [os.path.abspath('.')]
                with Timer().time() as timer:
                    with suppress_stdio(not loud):
                        with CrashChecker(reraise).guard() as crash_checker:
                            pcbasic.run('--interface=none')
            times[name] = timer.wall_time
            if crash_checker.crash or not output_checker.passed:
                if crash_checker.crash:
                    print('\033[01;37;41mEXCEPTION.\033[00;37m')
                    print('    %r' % crash_checker.crash)
                    crashed.append(name)
                elif not output_checker.known:
                    if output_checker.old_fail:
                        print('\033[00;33mfailed.\033[00;37m')
                    else:
                        print('\033[01;31mfailed.\033[00;37m')
                    if output_checker.old_fail:
                        oldfailed.append(name)
                    else:
                        failed.append(name)
                else:
                    print('\033[00;36maccepted.\033[00;37m')
                    knowfailed.append(name)
            else:
                print('\033[00;32mpassed.\033[00;37m')
            numtests += 1

    print()
    print(
        '\033[00mRan %d tests in %.2fs (wall) %.2fs (cpu):' %
        (numtests, overall_timer.wall_time, overall_timer.cpu_time)
    )
    if crashed:
        print('    %d exceptions: \033[01;37;41m%s\033[00m' % (len(crashed), ' '.join(crashed)))
    if failed:
        print('    %d new failures: \033[01;31m%s\033[00m' % (len(failed), ' '.join(failed)))
    if oldfailed:
        print('    %d old failures: \033[00;33m%s\033[00m' % (len(oldfailed), ' '.join(oldfailed)))
    if knowfailed:
        print('    %d accepts: \033[00;36m%s\033[00m' % (len(knowfailed), ' '.join(knowfailed)))
    numpass = numtests - len(failed) - len(knowfailed)- len(crashed) - len(oldfailed)
    if numpass:
        print('    %d passes' % numpass)

    print()
    slowtests = sorted(times.items(), key=lambda _p: _p[1], reverse=True)
    print('\033[00;37mSlowest tests:')
    print('    ' + '\n    '.join('{}: {:.1f}'.format(_k, _v) for _k, _v in slowtests[:SLOWSHOW]))

    # update slow-tests file
    if all and not fast:
        with open(SLOWTESTS, 'w') as slowfile:
            json.dump(dict(slowtests), slowfile)

    if cov:
        cov.stop()
        cov.save()
        cov.html_report()


if __name__ == '__main__':
    args = parse_args()
    run_tests(*args)
