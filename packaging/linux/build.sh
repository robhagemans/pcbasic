#!/bin/bash
ARCH=`uname -i`
NAME="pcbasic-$1-linux-$ARCH"

pyinstaller installer.spec

# add files to top level of archive
cp install.sh dist/install.sh
cp pcbasic.png dist/pcbasic.png
cp ../../README.md dist/README.md
cp ../../LICENSE.md dist/LICENSE.md
chmod ugo+x dist/install.sh

mv dist "$NAME"
tar cvfz $NAME.tgz $NAME

rm -rf build
rm -rf "$NAME"


