10 ' test RENUMbering an active error handler 
15 open "output.txt" for output as 1
20 on error goto 100
25 print#1, "before error"
30 color 1000 ' illegal function call
40 print#1, "after error"
45 close
50 end
100 print#1, "error handler"
110 stop
120 resume next

