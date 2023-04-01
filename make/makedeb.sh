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
cp ./run-pcbasic.py $DEBDIR/usr/local/bin/pcbasic

# wheel distribution
for PYVER in $(seq $LOWEST $HIGHEST); do
    mkdir -p $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages
done

echo "unpacking wheel"
wheel unpack dist/pcbasic-$VERSION-py2.py3-none-any.whl -d build/
mv build/pcbasic-$VERSION/* $DEBDIR/usr/local/lib/python3.$LOWEST/dist-packages

# link from other suported python versions
for PYVER in $(seq $(($LOWEST+1)) $HIGHEST); do
    echo "linking $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages"
    pushd $DEBDIR/usr/local/lib/python3.$PYVER/dist-packages > /dev/null
    ln -s ../../python3.$LOWEST/dist-packages/pcbasic .
    popd > /dev/null
done

echo "copying resources"

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

# hashes for package files
echo "calculating hashes"
mkdir -p $DEBDIR/DEBIAN
pushd $DEBDIR > /dev/null
find usr/ -exec md5sum '{}' \; >> DEBIAN/md5sums 2> /dev/null
popd > /dev/null

# DEBIAN/control file
cp build/resources/control $DEBDIR/DEBIAN/control

# calculate installed size
echo -n "Installed-Size: " >> $DEBDIR/DEBIAN/control
du -s build/python3-pcbasic_"$VERSION"_all/usr/ | awk '{print $1 }' >> $DEBDIR/DEBIAN/control

# build the deb
echo "building the .deb package"
dpkg-deb --root-owner-group -b $DEBDIR
mkdir dist
mv $DEBDIR.deb dist/

# # RPM package disabled - even after removing the clashes with `filesystem` this does not work
# # if someone can dedicate the time to setup and maintain an RPM build we can re-enable RPMs
#
# # build the rpm
# echo "building the .rpm package"
# cd dist
# # claims to need sudo but seems to get root owner correct without
# alien -g --to-rpm --keep-version python3-pcbasic_"$VERSION"_all.deb
# # remove standard directories from spec to avoid clash with `filesystem` package
# # discussions #211
# # following https://www.electricmonk.nl/log/2017/02/23/how-to-solve-rpms-created-by-alien-having-file-conflicts/
# # see also https://stackoverflow.com/questions/27172142/conflicts-with-file-from-package-filesystem-3-2
# RPMDIR="python3-pcbasic-$VERSION"
# cd "$RPMDIR"
#
# SPEC=`find python3-pcbasic-$VERSION-?.spec`
# sed -i 's#%dir "/"##' "$SPEC"
# sed -i 's#%dir "/usr/"##' "$SPEC"
# sed -i 's#%dir "/usr/local/"##' "$SPEC"
# sed -i 's#%dir "/usr/local/bin/"##' "$SPEC"
# sed -i 's#%dir "/usr/local/lib/"##' "$SPEC"
# sed -i 's#%dir "/usr/local/share/"##' "$SPEC"
# sed -i 's#%dir "/usr/local/share/applications/"##' "$SPEC"
# #sed -i 's#%dir "/usr/local/share/icons/"##' "$SPEC"
# sed -i 's#%dir "/usr/local/share/man/"##' "$SPEC"
#
# rpmbuild --target=noarch --buildroot `pwd` -bb $SPEC
# cd ..
#
# cd ..
