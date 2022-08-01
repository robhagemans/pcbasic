#!/bin/bash

# PC-BASIC - makedeb.sh
# Linux packaging script
#
# (c) 2022 Rob Hagemans
# This file is released under the GNU GPL version 3 or later.


# pc-basic version number
VERSION=$1
if [ -z $VERSION ]; then
    echo "usage: makedeb.sh VERSION"
    exit 1
fi

# python versions supported
LOWEST=6
HIGHEST=11

# to be run from repo root
DEBDIR=build/python3-pcbasic_"$VERSION"_all

# entry point
mkdir -p $DEBDIR/usr/local/bin
cp ./pc-basic $DEBDIR/usr/local/bin/pcbasic

# wheel distribution
for PYVER in $(seq $LOWEST $HIGHEST); do
    mkdir -p $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages
done
wheel unpack dist/pcbasic-$VERSION-py2.py3-none-any.whl -d build/
mv build/pcbasic-$VERSION/* $DEBDIR/usr/local/lib/python3.$LOWEST/dist-packages

# link from other suported python versions
for PYVER in $(seq $(($LOWEST+1)) $HIGHEST); do
    echo "linking $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages/pcbasic"
    pushd $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages > /dev/null
    ln -s ../../python3.$LOWEST/dist-packages/pcbasic .
    popd > /dev/null
done

# desktop file
mkdir -p $DEBDIR/usr/local/share/applications
cp build/resources/pcbasic.desktop $DEBDIR/usr/local/share/applications

# icon
mkdir -p $DEBDIR/usr/local/share/icons
cp build/resources/pcbasic.png $DEBDIR/usr/local/share/icons

# manpage
mkdir -p $DEBDIR/usr/local/share/man
cp build/doc/pcbasic.1.gz $DEBDIR/usr/local/share/man

# documentation
#mkdir -p $DEBDIR/usr/local/share/doc/pcbasic
#cp build/doc/PC-BASIC_documentation.html $DEBDIR/usr/local/share/doc/pcbasic

# package files
mkdir -p $DEBDIR/DEBIAN

find usr/ -exec md5sum '{}' \; >> DEBIAN/md5sums

# DEBIAN/control file
cp build/resources/control $DEBDIR/DEBIAN/control

# calculate installed size
echo -n "Installed-Size: " >> $DEBDIR/DEBIAN/control
du -s build/python3-pcbasic_2.0.5_all/usr/ | awk '{print $1 }' >> $DEBDIR/DEBIAN/control

# build the deb
dpkg-deb --root-owner-group -b $DEBDIR
mkdir dist
mv $DEBDIR.deb dist/

# build the rpm
cd dist
# claims to need sudo but seem s to get root owner correct without
alien --to-rpm --keep-version python3-pcbasic_"$VERSION"_all.deb
cd ..
