#!/bin/bash
for file in ../pcbasic/*.py; do pylint -E --ignored-modules=pygame,numpy,pygame.mixer --disable=maybe-no-member,too-many-function-args $file; done
