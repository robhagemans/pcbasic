#!/bin/bash
name="$1"
cp -R TEST/ "$name"/
rm -r "$name/model"
