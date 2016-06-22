"""
PC-BASIC - audio_none.py
Null sound implementation

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime
import Queue

from ..basic import signals
from . import base


class AudioNone(base.AudioPlugin):
    """Null audio plugin."""
