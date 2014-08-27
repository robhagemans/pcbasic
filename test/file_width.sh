#!/bin/bash
name=FILEWIDT
cd output/$name
echo "Running file width tests..."
rm FILEW*
../../../pcbasic -bq "../../$name.BAS"
pass=1
for file in *
do
  diff "$file" "../../model/$name/$file"
  if [ $? -ne 0 ]
  then
     echo "$file: FAIL";
     pass=0
  fi
done
if [ $pass -ne 1 ]
then
     echo "Test FAILED";
else
     echo "Test passed";
fi

