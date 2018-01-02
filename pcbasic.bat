@echo off
if exist launcher.exe (
    launcher.exe python -m pcbasic %*
) else (
    echo WARNING: ANSIpipe launcher not found, command-line output may be garbled
    python -m pcbasic %*
)
