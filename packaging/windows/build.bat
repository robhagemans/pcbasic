pyinstaller installer-console.spec
move dist\pcbasic\pcbasic.exe pcbasic.com
rmdir /s /q build
rmdir /s /q dist
pyinstaller installer.spec
move pcbasic.com dist\pcbasic\pcbasic.com
makensis pcbasic.nsi
ren pcbasic-win32.exe pcbasic-%1-win32.exe
rmdir /s /q build
rmdir /s /q dist

