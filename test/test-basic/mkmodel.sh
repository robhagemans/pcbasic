#!/bin/bash
name="$1"
cd "$name"
mkdir model
cp -R * model/
cd model/
# remove model/model created by cp -R
rm -r model/
# remove the output directory which was copied along if it existed
rm -r output/
GWBASIC=$(cat ../../gwbasicdir)
echo "gwbasic dir: $GWBASIC"
dosbox -c "MOUNT C ." -c "MOUNT E $GWBASIC" -c "C:" -c "E:\GWBASIC\GWBASIC TEST.BAS" -c "EXIT"
cd ..
for file in *
do
  rm "model/$file"
done
cd ..
