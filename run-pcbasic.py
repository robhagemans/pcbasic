#!/usr/bin/env python3

"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pcbasic import main, script_entry_point_guard

if __name__ == '__main__':
    with script_entry_point_guard():
        main()
