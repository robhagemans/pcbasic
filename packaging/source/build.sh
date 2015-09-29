#!/bin/bash
VERSION=$(cat ../../pcbasic/data/version.txt)
NAME="pcbasic-$VERSION"
echo "running prepare script"
pushd ../..
python setup.py build_docs
popd
echo "building $NAME"
rsync -rvp ../.. pcbasic/ --delete --exclude-from=excludes --delete-excluded
cp install.sh pcbasic/
cp pcbasic.png pcbasic/
cp pcbasic.bat pcbasic/
cp winbuild.bat pcbasic/
mv pcbasic $NAME
tar cvfz "$NAME.tgz" "$NAME/"
rm -rf "$NAME/"
