"""
PC-BASIC - docsrc
Documentation builder and source

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .usage import makeusage
from .man import makeman
from .doc import makedoc


def make_all_docs(output_dir):
    """Build all documentation files."""
    makeusage()
    makeman(output_dir)
    makedoc(output_dir, 'PC-BASIC_documentation.html')
