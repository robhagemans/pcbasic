#!/bin/bash
name="$1"
cp -R TEST-tnd/ "$name"
rm -r "$name/model"
