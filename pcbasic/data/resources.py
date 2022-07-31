"""
PC-BASIC - data package
Fonts, codepages and BASIC resources

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import json
import os
from ..compat import resources
import logging


###############################################################################
# exceptions

class ResourceFailed(Exception):
    """Failed to load resource"""

    def __init__(self, name=u''):
        self._message = u'Failed to load {0}'.format(name)

    def __repr__(self):
        return self._message

    __str__ = __repr__


###############################################################################
# resource readers

def get_data(pattern, **kwargs):
    """Wrapper for resource_string."""
    dir, _, name = pattern.format(**kwargs).partition('/')
    try:
        # this should return None if not available, I thought, but it doesn't
        resource = resources.read_binary(__package__ + '.' + dir.replace('/', '.'), name)
    except EnvironmentError:
        raise ResourceFailed(name)
    if resource is None:
        raise ResourceFailed(name)
    return resource

def listdir(dirname):
    """Wrapper for resource_listdir."""
    return list(resources.contents(__package__ + '.' + dirname))

def read_program_file(name):
    """Read a bundled BASIC program file."""
    return get_data(PROGRAM_PATTERN, path=PROGRAM_DIR, name=name)


###############################################################################
# bundled programs

PROGRAM_DIR = u'programs'
PROGRAM_PATTERN = u'{path}/{name}'
PROGRAMS = (
    name
    for name in listdir(PROGRAM_DIR)
    if name.lower().endswith(u'.bas')
)
