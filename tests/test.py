#!/usr/bin/env python3
"""
PC-BASIC test script

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
from contextlib import contextmanager

from .unit import run_unit_tests
from .basic import run_basic_tests

# specify locations relative to this file
HERE = os.path.dirname(os.path.abspath(__file__))

# unittest verbosity, increase for more info on what is running
VERBOSITY = 1


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
    unit = contained(args, '--unit')
    return {
        'all': all,
        'fast': fast,
        'loud': loud,
        'reraise': reraise,
        'coverage': cover,
        'unit': unit,
        'tests': args,
    }


class Coverage(object):

    def __init__(self, cover):
        self._on = cover

    @contextmanager
    def track(self):
        if self._on:
            import coverage
            cov = coverage.coverage(omit=[os.path.join(HERE, '*'), '/usr/local/lib/*'])
            cov.start()
            yield self
            cov.stop()
            cov.save()
            cov.html_report()
        else:
            yield


def test_main():
    arg_dict = parse_args()
    with Coverage(arg_dict['coverage']).track():
        run_basic_tests(**arg_dict)
        if arg_dict['all'] or arg_dict['unit']:
            run_unit_tests()

if __name__ == '__main__':
    test_main()
