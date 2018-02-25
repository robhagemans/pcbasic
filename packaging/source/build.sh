#!/bin/bash
VERSION=$(../../pcbasic.sh -v)
NAME="pcbasic-$VERSION"
echo "running prepare script"
pushd ../..
python setup.py build_docs
popd
echo "building $NAME"
rsync -rvp ../.. pcbasic/ --delete --exclude-from=excludes --delete-excluded
cp install.sh pcbasic/
cp ../windows/launcher.exe pcbasic/
cp pcbasic.png pcbasic/
mv pcbasic $NAME
tar cvfz "$NAME.tgz" "$NAME/"
rm -rf "$NAME/"
