#!/bin/bash

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
wheel unpack dist/pcbasic-$VERSION-py2.py3-none-any.whl -d dist/
mv dist/pcbasic-$VERSION/* $DEBDIR/usr/local/lib/python3.$LOWEST/dist-packages

# link from other suported python versions
for PYVER in $(seq $(($LOWEST+1)) $HIGHEST); do
    pushd $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages
    ln -s ../../python3.$LOWEST/dist-packages/pcbasic .
    popd #cd ../../../../../..
done

# desktop file
mkdir -p $DEBDIR/usr/local/share/applications
cp resources/pcbasic.desktop $DEBDIR/usr/local/share/applications

# icon
mkdir -p $DEBDIR/usr/local/share/icons
cp resources/pcbasic.png $DEBDIR/usr/local/share/icons

# manpage
mkdir -p $DEBDIR/usr/local/share/man
cp resources/pcbasic.1.gz $DEBDIR/usr/local/share/man


# package files
mkdir -p $DEBDIR/DEBIAN

pushd $DEBDIR
find usr/ -exec md5sum '{}' \; >> DEBIAN/md5sums
popd

cat << EOF > $DEBDIR/DEBIAN/control
Package: python3-pcbasic
Version: $VERSION
License: GPLv3
Vendor: none
Architecture: all
Maintainer: <rob@bandicoot>
Depends: python3-pkg-resources,python3-serial,python3-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0
Section: default
Priority: extra
Homepage: http://pc-basic.org
Description: A free, cross-platform emulator for the GW-BASIC family of interpreters.
EOF

#TODO
#Installed-Size: 6845
du -s build/python3-pcbasic_2.0.5_all/usr/

# build the deb
dpkg-deb --root-owner-group -b $DEBDIR
mkdir dist
mv $DEBDIR.deb dist/

# build the rpm
cd dist
# claims to need sudo but seem s to get root owner correct without
alien --to-rpm --keep-version python3-pcbasic_"$VERSION"_all.deb
cd ..
