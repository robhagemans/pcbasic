pyinstaller installer.spec
cd ..\..\ansipipe
make launcher
cd ..\packaging\windows
move ..\..\ansipipe\launcher.exe dist\pcbasic\pcbasic.com
makensis pcbasic.nsi
ren pcbasic-win32.exe pcbasic-%1-win32.exe
rmdir /s /q build
rmdir /s /q dist

