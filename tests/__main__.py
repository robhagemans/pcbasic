import os
import sys

from .test import test_main

# make pcbasic package accessible if run from top level
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [HERE] + sys.path

# run tests
test_main()
