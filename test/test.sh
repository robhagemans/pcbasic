#!/bin/bash
name=$1
cd output/$name
echo "Running test $name..."
#rm *
../../../pcbasic -bq "../../$name.BAS" > /dev/null
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

