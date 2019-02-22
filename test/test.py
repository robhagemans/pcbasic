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


def prepare_outputs(dirname):
    output_dir = os.path.join(dirname, 'output')
    model_dir = os.path.join(dirname, 'model')
    known_dir = os.path.join(dirname, 'known')
    old_fail = False
    if os.path.isdir(output_dir):
        old_fail = True
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)
    for filename in os.listdir(dirname):
        if os.path.isfile(os.path.join(dirname, filename)):
            shutil.copy(os.path.join(dirname, filename), os.path.join(output_dir, filename))
    return output_dir, model_dir, known_dir

def compare_outputs(dirname, output_dir, model_dir, known_dir):
    passed = True
    known = True
    failfiles = []
    for path, dirs, files in os.walk(model_dir):
        for f in files:
            if f.endswith('.pyc'):
                continue
            filename = os.path.join(path[len(model_dir)+1:], f)
            if (not is_same(os.path.join(output_dir, filename), os.path.join(model_dir, filename))
                    and not os.path.isfile(os.path.join(dirname, filename))):
                failfiles.append(filename)
                known = (
                    os.path.isdir(known_dir) and
                    is_same(os.path.join(output_dir, filename), os.path.join(known_dir, filename))
                )
                passed = False
    for path, dirs, files in os.walk(output_dir):
        for f in files:
            if f.endswith('.pyc'):
                continue
            filename = os.path.join(path[len(output_dir)+1:], f)
            if (
                    not os.path.isfile(os.path.join(model_dir, filename))
                    and not os.path.isfile(os.path.join(dirname, filename))
                ):
                failfiles.append(filename)
                passed = False
                known = False
    return passed, known, failfiles


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

    start_time = time.time()
    start_clock = time.clock()

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
        output_dir, model_dir, known_dir = prepare_outputs(dirname)
        top = os.getcwd()
        os.chdir(output_dir)
        sys.stdout.flush()
        # we need to include the output dir in the PYTHONPATH for it to find extension modules
        sys.path = PYTHONPATH + [os.path.abspath('.')]
        test_start_time = time.time()
        # -----------------------------------------------------------
        # suppress output and logging and call PC-BASIC
        with suppress_stdio(not loud):
            crash = None
            try:
                pcbasic.run('--interface=none')
            except Exception as e:
                crash = e
                if reraise:
                    raise
        # -----------------------------------------------------------
        times[name] = time.time() - test_start_time
        os.chdir(top)

        passed, known, failfiles = compare_outputs(dirname, output_dir, model_dir, known_dir)

        if crash or not passed:
            if crash:
                print('\033[01;37;41mEXCEPTION.\033[00;37m')
                print('    %r' % crash)
                crashed.append(name)
            elif not known:
                if old_fail:
                    print('\033[00;33mfailed.\033[00;37m')
                else:
                    print('\033[01;31mfailed.\033[00;37m')
                if old_fail:
                    oldfailed.append(name)
                else:
                    failed.append(name)
            else:
                print('\033[00;36maccepted.\033[00;37m')
                knowfailed.append(name)
        else:
            print('\033[00;32mpassed.\033[00;37m')
            shutil.rmtree(output_dir)
        numtests += 1

    print()
    print(
        '\033[00mRan %d tests in %.2fs (wall) %.2fs (cpu):' %
        (numtests, time.time() - start_time, time.clock() - start_clock)
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
