#!/bin/bash
name="$1"
cd "$name"
mkdir model
cp -R * model/
cd model/
# remove model/model created by cp -R
rm -r model/
GWBASIC=$(cat ../../gwbasicdir)
echo "gwbasic dir: $GWBASIC"
dosbox -c "MOUNT C ." -c "MOUNT E $GWBASIC" -c "C:" -c "E:\GWBASIC\GWBASIC TEST.BAS" -c "EXIT"
cd ../..
