#!/bin/bash
VERSION=$(cat ../../data/VERSION)
NAME="pcbasic-$VERSION"
echo "building $NAME"
rsync -rvp ../.. pcbasic/ --delete --exclude-from=excludes --delete-excluded
cp install.sh pcbasic/
cp pcbasic.png pcbasic/
cp pcbasic.bat pcbasic/
cp ansipipe.exe pcbasic/
mv pcbasic $NAME
tar cvfz "$NAME.tgz" "$NAME/"
rm -rf "$NAME/"
