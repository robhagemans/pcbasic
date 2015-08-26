#!/bin/bash
if [ -z $1 ]
then
     echo "Usage: test.sh TESTNAME"
     exit
fi
name=$1
echo -n "Running test $name... "
if [ ! -e $name ]
then
     echo "no such test."
     exit
fi
mkdir "$name/output"
cp "$name"/* "$name/output" 2>/dev/null
pushd "$name/output" > /dev/null
../../../pcbasic.py
popd > /dev/null
pass=1
for file in "$name/model"/*
do
  filename=$(basename "$file")
  diff "$name/output/$filename" "$name/model/$filename"
  if [ $? -ne 0 ]
  then
     echo "$filename: FAIL";
     pass=0
  fi
done
for file in "$name/output"/*
do
  filename=$(basename "$file")
  if [ ! -e "$name/model/$filename" ]
  then
    echo "$filename: FAIL (not in model)"
    pass=0
  fi
done
if [ $pass -ne 1 ]
then
     echo "FAILED.";
else
     echo "passed.";
     rm -r $name/output
fi
