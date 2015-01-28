pyinstaller installer.spec
copy ansipipe.com dist\pcbasic\pcbasic.com
makensis pcbasic.nsi
ren pcbasic-win32.exe pcbasic-%1-win32.exe
rmdir /s /q build
rmdir /s /q dist

