#!/bin/bash
if [ -z $1 ]
then
     echo "Usage: test.sh TESTNAME"
     exit
fi 
name=$1
echo -n "Running test $name... "
if [ ! -e $name.BAS ]
then
     echo "no such test"
     exit
fi
mkdir output/$name
pushd output/$name > /dev/null
../../../pcbasic.py -q "../../$name.BAS" --preset=tandy --font=freedos
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
     echo "FAILED.";
else
     echo "passed.";
     popd > /dev/null
     rm -r output/$name
fi

