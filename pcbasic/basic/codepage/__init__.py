"""
PC-BASIC - codepage package
Codepage definitions

(c) 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkgutil

codepages = pkgutil.get_data(__name__, 'list.txt').splitlines()


class ResourceFailed(Exception):
    """Failed to load codepage."""
    def __str__(self):
        return self.__doc__


def read_file(codepage_name):
    """Retrieve contents of codepage file."""
    try:
        resource = pkgutil.get_data(__name__, codepage_name + '.ucp')
    except EnvironmentError:
        raise ResourceFailed()
    if resource is None:
        raise ResourceFailed()
    return resource
