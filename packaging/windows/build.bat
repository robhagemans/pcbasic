pyinstaller installer.spec
makensis pcbasic.nsi
ren pc-basic-win32.exe pc-basic-%1-win32.exe
rmdir /s /q build
rmdir /s /q dist
