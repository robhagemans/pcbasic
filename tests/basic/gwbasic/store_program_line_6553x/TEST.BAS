10 ' test frame - store program lines 65530 or higher
20 on error goto 100
25 open "errors.txt" for output as 1
30 stop
100 print#1, "error "; err; " in "; erl
110 resume next

