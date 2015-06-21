set /p VERSION=<..\..\data\VERSION
pyinstaller installer.spec
cd ..\..\ansipipe
gcc -s launcher.c -o launcher -DSUPPRESS_STDERR
cd ..\packaging\windows
move ..\..\ansipipe\launcher.exe dist\pcbasic\pcbasic.com
makensis pcbasic.nsi
ren pcbasic-win32.exe pcbasic-%VERSION%-win32.exe
rmdir /s /q build
rmdir /s /q dist

