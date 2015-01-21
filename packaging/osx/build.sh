NAME="pcbasic-$1-osx"
pyinstaller installer.spec
hdiutil create -srcfolder PC-BASIC.app -volname "PC-BASIC release $1" $NAME.uncompressed.dmg
hdiutil convert $NAME.uncompressed.dmg -format UDZO -imagekey zlib-level=9 -o $NAME.dmg
rm $NAME.uncompressed.dmg
rm -rf PC-BASIC.app
