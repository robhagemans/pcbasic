#!/bin/bash
for file in ../basic/*.py ../interface/*.py ../pcbasic.py; do pylint -E --ignored-modules=pygame,numpy,pygame.mixer --disable=too-many-function-args $file; done
