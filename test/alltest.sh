#!/bin/bash
for test in $(ls -d */)
do
    ./test.sh $test
done
