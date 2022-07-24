"""
PC-BASIC - data package
Fonts, codepages and BASIC resources

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import json
import os
import pkg_resources
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
    name = pattern.format(**kwargs)
    try:
        # this should return None if not available, I thought, but it doesn't
        resource = pkg_resources.resource_string(__name__, name)
    except EnvironmentError:
        raise ResourceFailed(name)
    if resource is None:
        raise ResourceFailed(name)
    return resource

def listdir(dirname):
    """Wrapper for resource_listdir."""
    try:
        return pkg_resources.resource_listdir(__name__, dirname)
    except NotImplementedError as e:
        # this happens with cx_Freeze packages now
        # as the global ResourceManager is a NullProvider
        # not clear why but this works around
        logging.debug('working around pkg_resources error: %s', e)
        return os.listdir(os.path.join(os.path.dirname(__file__), dirname))

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
