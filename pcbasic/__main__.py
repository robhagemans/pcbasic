"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .main import main, script_entry_point_guard

with script_entry_point_guard():
    main()
