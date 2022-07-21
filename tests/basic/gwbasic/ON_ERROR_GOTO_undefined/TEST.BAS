10 ' test ON ERROR GOTO with undefined line number 
15 open "errors.txt" for output as 1
20 on error goto 100
30 on error goto 200 ' undefined line number
40 end
100 print#1, err, erl
110 resume next

