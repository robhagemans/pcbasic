"""
PC-BASIC tests.unit
unit tests

(c) 2015--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys

# make pcbasic package accessible
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [os.path.join(HERE, '..', '..')] + sys.path


# unittest verbosity, increase for more info on what is running
VERBOSITY = 1


def run_unit_tests():
    import pcbasic
    sys.stderr.write('Running unit tests: ')
    with pcbasic.compat.stdio.quiet('stdout'):
        import unittest
        suite = unittest.loader.defaultTestLoader.discover(HERE, 'test*.py', None)
        runner = unittest.TextTestRunner(verbosity=VERBOSITY)
        runner.run(suite)
