10 ' test ON event syntax error 
20 open"errors.txt"for output as 1
30 on error goto 1000
35 ' syntax error
40 ON PRINT GOSUB 2000
45 ' illegal function call
50 AUTO 10,
55 ' missing operand
60 PRINT USING "\\";
99 close:end
1000 print#1, err, erl
1010 resume next
2000 return

