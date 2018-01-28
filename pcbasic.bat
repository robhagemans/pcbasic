@echo off

rem PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter
rem (c) 2013--2018 Rob Hagemans
rem This file is released under the GNU GPL version 3 or later.

setlocal
set PYTHONPATH=%PYTHONPATH%;%~dp0

if exist launcher.exe (
    launcher.exe python -m pcbasic %*
) else (
    echo WARNING: ANSIpipe launcher not found, command-line output may be garbled
    python -m pcbasic %*
)
