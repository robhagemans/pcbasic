#!/bin/bash
rsync -rvp ../.. pcbasic/ --delete --exclude-from=excludes --delete-excluded
cp install.sh pcbasic/
cp pcbasic.png pcbasic/
mv pcbasic "pc-basic-$1-src"
tar cvfz "pc-basic-$1-src.tgz" "pc-basic-$1-src/"
rm -rf "pc-basic-$1-src/"
