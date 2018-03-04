"""
PC-BASIC - data package
Fonts, codepages and BASIC resources

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkg_resources

PROGRAM_DIR = u'programs'
PROGRAM_PATTERN = u'{path}/{name}'
PROGRAMS = (name for name in pkg_resources.resource_listdir(__name__, PROGRAM_DIR) if name.lower().endswith(u'.bas'))

ICON = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0],
    [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0],
    [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0],
    [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0],
    [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0],
    [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]


###############################################################################
# exceptions

class ResourceFailed(Exception):
    """Failed to load resource"""

    def __init__(self, name=u''):
        self._message = u'Failed to load {0}'.format(name)

    def __str__(self):
        return self._message


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

def read_program_file(name):
    """Read a bundled BASIC program file."""
    return get_data(PROGRAM_PATTERN, path=PROGRAM_DIR, name=name)
