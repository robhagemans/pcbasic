python ..\..\run.py -v > version.txt
set /p VERSION=<version.txt
del version.txt
pyinstaller installer.spec
cd ..\..\pcbasic\ansipipe
gcc -s launcher.c -o launcher
cd ..\..\packaging\windows
move ..\..\pcbasic\ansipipe\launcher.exe dist\pcbasic\pcbasic.com
makensis pcbasic.nsi
ren pcbasic-win32.exe pcbasic-%VERSION%-win32.exe
rmdir /s /q build
rmdir /s /q dist
