"""
PC-BASIC - data.programs
Bundled BASIC programs

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ...compat import resources


# list of available programs
PROGRAMS = tuple(
    name
    for name in resources.contents(__package__)
    if name.lower().endswith('.bas') and resources.is_resource(__package__, name)
)


def read_program_file(name):
    """Read a bundled BASIC program file."""
    return resources.read_binary(__package__, name)
