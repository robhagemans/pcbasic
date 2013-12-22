#
# PC-BASIC 3.23 - glob.py
#
# Globals 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# device implementations
scrn = None
lpt1 = None
lpt2 = None
lpt3 = None
com1 = None
com2 = None

# graphics and sound implementations
graph = None
sound = None


devices = {}
output_devices = {}
random_devices = {}

# ascii CR/LF
endl='\x0d\x0a'

# debug mode - enables DEBUG keyword
debug=False

# pre-defined PEEK outputs
peek_values={}


# 'free memory' as reported by FRE
total_mem = 60300    
free_mem = total_mem    
    





