#!/bin/sh
# PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter
# (c) 2013, 2014, 2015, 2016, 2017 Rob Hagemans
# This file is released under the GNU GPL version 3 or later.
cd "$(dirname -- "$0")"
/usr/bin/env python2 -m pcbasic "$@"
