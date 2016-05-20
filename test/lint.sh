#!/bin/bash
exclude=../pcbasic/ansipipe/example.py
for file in ../pcbasic/*.py ../pcbasic/*/*.py
do
  if [[ "$file" != "$exclude" ]]
  then
    echo "$file"
    pylint --ignored-modules=pygame,numpy,pygame.mixer --ignored-classes=Serial,pygame.Surface "$file"
  fi
done
