#!/bin/bash
./makeman.py options.html | groff -t -e -mandoc -Tascii | col -bx > ../pcbasic/data/usage.txt
