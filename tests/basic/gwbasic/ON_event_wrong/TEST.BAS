10 ' test ON event syntax error 
20 open"errors.txt"for output as 1
30 on error goto 1000
35 'this is an error
40 ON PRINT GOSUB 100
99 close:end
100 return
1000 print#1, err, erl
1010 resume next

