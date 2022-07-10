@echo off

rem PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter
rem (c) 2013--2022 Rob Hagemans
rem This file is released under the GNU GPL version 3 or later.

setlocal
set PYTHONPATH=%PYTHONPATH%;%~dp0

python -m pcbasic %*
