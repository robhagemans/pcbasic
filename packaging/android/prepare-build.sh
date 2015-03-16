#!/bin/bash
rsync -rvp pc-basic build/ --delete --exclude='patches/' --exclude='test/' --exclude='data/*.SAV' --exclude='*.pyc' --exclude='*.pyo' --exclude='*~' --exclude='.git*' --delete-excluded
cp build/pc-basic/pcbasic build/pc-basic/main.py
