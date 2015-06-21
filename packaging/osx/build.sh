#!/bin/bash
VERSION=$(cat ../../data/VERSION)
NAME="pcbasic-$VERSION-osx"
pyinstaller installer.spec
# replace executable started by Finder with workaround script to set cwd
cp launcher.sh dist/PC-BASIC.app/Contents/MacOS/
cp Info.plist dist/PC-BASIC.app/Contents/
# build compressed DMG image
hdiutil create -srcfolder dist/PC-BASIC.app -volname "PC-BASIC release $VERSION" $NAME.uncompressed.dmg
hdiutil convert $NAME.uncompressed.dmg -format UDZO -imagekey zlib-level=9 -o $NAME.dmg
rm $NAME.uncompressed.dmg
rm -rf dist
rm -rf build
