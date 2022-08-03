10 ' test frame for errors, check DEF FN in direct mode 
15 open "errors.txt" for output as 1
20 on error goto 100
30 stop
100 print#1, err, erl
110 resume next

