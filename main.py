#!/usr/bin/env python

#
# PC-BASIC 3.23 
# Entry point for Android
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

def main():
    while True:
        try:
            import pcbasic
            pcbasic.main()
            break
        except Exception:
            reload(pcbasic)       

if __name__ == "__main__":
    main()
