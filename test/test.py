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
from copy import copy, deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))


# make pcbasic package accessible
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
pythonpath = copy(sys.path)

def is_same(file1, file2):
    try:
        return filecmp.cmp(file1, file2, shallow=False)
    except EnvironmentError:
        return False

def count_diff(file1, file2):
    lines1 = open(file1, 'rb').readlines()
    lines2 = open(file2, 'rb').readlines()
    n = len(lines1)
    count = 0
    for one, two in zip(lines1, lines2):
        if one != two:
            count += 1
    return n, count

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

args = sys.argv[1:]

do_suppress = not contained(args, '--loud')
reraise = contained(args, '--reraise')

if contained(args, '--coverage'):
    import coverage
    cov = coverage.coverage()
    cov.start()
else:
    cov = None

if not args or '--all' in args:
    args = [
        os.path.join('basic', _preset, _test)
        for _preset in os.listdir(os.path.join(HERE, 'basic'))
        for _test in sorted(os.listdir(os.path.join(HERE, 'basic', _preset)))
    ]

numtests = 0
failed = []
knowfailed = []


import pcbasic

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
    output_dir = os.path.join(dirname, 'output')
    model_dir = os.path.join(dirname, 'model')
    known_dir = os.path.join(dirname, 'known')
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)
    for filename in os.listdir(dirname):
        if os.path.isfile(os.path.join(dirname, filename)):
            shutil.copy(os.path.join(dirname, filename), os.path.join(output_dir, filename))
    top = os.getcwd()
    os.chdir(output_dir)
    sys.stdout.flush()
    # we need to include the output dir in the PYTHONPATH for it to find extension modules
    sys.path = pythonpath + [os.path.abspath('.')]
    # -----------------------------------------------------------
    # suppress output and logging and call PC-BASIC
    with suppress_stdio(do_suppress):
        crash = None
        try:
            pcbasic.run('--interface=none')
        except Exception as e:
            crash = e
            if reraise:
                raise
    # -----------------------------------------------------------
    os.chdir(top)
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
    if crash or not passed:
        if crash:
            print('\033[01;31mEXCEPTION.\033[00;37m')
            print('    %r' % crash)
            failed.append(name)
        elif not known:
            print('\033[01;31mfailed.\033[00;37m')
            for failname in failfiles:
                try:
                    n, count = count_diff(
                        os.path.join(output_dir, failname), os.path.join(model_dir, failname)
                    )
                    pct = 100.*count/float(n) if n != 0 else 0
                    print('    %s: %d lines, %d differences (%3.2f %%)' % (failname, n, count, pct))
                except EnvironmentError as e:
                    print('    %s: %s' % (failname, e))
            failed.append(name)
        else:
            print('\033[00;36mknown failure.\033[00;37m')
            for failname in failfiles:
                try:
                    n, count = count_diff(
                        os.path.join(output_dir, failname), os.path.join(model_dir, failname)
                    )
                    pct = 100.*count/float(n) if n != 0 else 0
                    print('    %s: %d lines, %d differences (%3.2f %%)' % (failname, n, count, pct))
                except EnvironmentError as e:
                    print('    %s: %s' % (failname, e))
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
if failed:
    print('    %d new failures: \033[01;31m%s\033[00m' % (len(failed), ' '.join(failed)))
if knowfailed:
    print('    %d known failures: \033[00;36m%s\033[00m' % (len(knowfailed), ' '.join(knowfailed)))
numpass = numtests - len(failed) - len(knowfailed)
if numpass:
    print('    %d passes' % numpass)

if cov:
    cov.stop()
    cov.save()
    cov.html_report()
