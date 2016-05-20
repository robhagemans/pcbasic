#!/bin/bash
exclude=../pcbasic/ansipipe/example.py
for file in ../pcbasic/*.py ../pcbasic/*/*.py
do
  if [[ "$file" != "$exclude" ]]
  then
    echo "$file"
    pylint -E --ignored-modules=pygame,numpy,pygame.mixer --enable=cyclic-import,relative-import --disable=too-many-function-args "$file"
  fi
done
