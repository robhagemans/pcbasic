#!/bin/bash
if [ -z $1 ]
then
    echo "Usage: test.sh TESTNAME [TESTNAME] ..."
    exit
fi
numtests=0
numfail=0
numknown=0
failed=
knowfailed=
for name in $@
do
    echo -n "Running test $name... "
    if [ ! -e $name ]
    then
        echo "no such test."
        exit
    fi
    if [ -e "$name/output" ]
    then
        rm -r "$name/output"
    fi
    mkdir "$name/output"
    cp "$name"/* "$name/output" 2>/dev/null
    pushd "$name/output" > /dev/null
    ../../../run-pcbasic.py --interface=none >/dev/null
    popd > /dev/null
    pass=1
    known=1
    for file in "$name/model"/*
    do
        filename=$(basename "$file")
        diff "$name/output/$filename" "$name/model/$filename"
        if [ $? -ne 0 ]
        then
            if [ -d "$name/known" ]
            then
                diff "$name/output/$filename" "$name/known/$filename"
                if [ $? -ne 0 ]
                then
                    echo "$filename: FAIL";
                    known=0
                else
                    echo "$filename: known failure";
                fi
            else
                echo "$filename: FAIL";
                known=0
            fi
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
            known=0
        fi
    done
    if [ $pass -ne 1 ]
    then
        if [ $known -ne 1 ]
        then
            echo "FAILED.";
            failed="$failed $name"
            numfail=$((numfail+1))
        else
            echo "known failure.";
            numknown=$((numknown+1))
            knowfailed="$knowfailed $name"
        fi
    else
        echo "passed.";
        rm -r $name/output
    fi
    numtests=$((numtests+1))
done
echo
echo "Ran $numtests tests:"
if [ $numfail -ne 0 ]
then
    echo "    $numfail new failures: $failed"
fi
if [ $numknown -ne 0 ]
then
    echo "    $numknown known failures: $knowfailed"
fi
numpass=$((numtests-numknown-numfail))
if [ $numpass -ne 0 ]
then
    echo "    $numpass passes"
fi
