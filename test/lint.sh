#!/bin/bash
for file in ../pcbasic/*.py ../pcbasic/*/*.py; do pylint -E --ignored-modules=pygame,numpy,pygame.mixer --enable=cyclic-import,relative-import --disable=too-many-function-args $file; done
