10 ' test ON event syntax error 
20 open"errors.txt"for output as 1
30 on error goto 1000
35 ' syntax error
40 ON PRINT GOSUB 2000
45 ' illegal function call
50 AUTO 10,
55 ' missing operand
60 PRINT USING "\\";
65 ' syntax error
70 OPEN "test.dat" FOR OUTPUT LOCK READ PRINT AS 1
71 OPEN "test.dat" FOR OUTPUT LOCK PRINT AS 2
75 ' missing operand
80 screen 1
81 LINE (10,10)-(20,20),
82 screen 0 
85 ' syntax error
90 a$="12345"
91 MID$[a$,1,1] = "a"
99 close:end
1000 print#1, err, erl
1010 resume next
2000 return

