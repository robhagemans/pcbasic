pyinstaller installer.spec
hdiutil create -srcfolder PC-BASIC.app -volname "PC-BASIC release $1" pc-basic-$1-osx.uncompressed.dmg
hdiutil convert pc-basic-$1-osx.uncompressed.dmg -format UDZO -imagekey zlib-level=9 -o pc-basic-$1-osx.dmg
rm pc-basic-$1-osx.uncompressed.dmg
rm -rf PC-BASIC.app
