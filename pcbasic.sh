#!/bin/sh

# PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter
# (c) 2013--2018 Rob Hagemans
# This file is released under the GNU GPL version 3 or later.

SCRIPTDIR="$(dirname -- "$0")"
export PYTHONPATH="$PYTHONPATH":"$SCRIPTDIR"

/usr/bin/env python2 -m pcbasic "$@"
