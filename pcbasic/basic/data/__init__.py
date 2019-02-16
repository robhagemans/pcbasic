"""
PC-BASIC - data

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pkg_resources import resource_string
import json

_METADATA = json.loads(resource_string(__name__, 'meta.json'))
NAME, VERSION, AUTHOR, COPYRIGHT = (_METADATA[_key] for _key in (
    'name', 'version', 'author', 'copyright'
))
