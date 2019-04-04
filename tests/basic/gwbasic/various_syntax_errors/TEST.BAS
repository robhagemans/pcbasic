10 ' test assorted statements raising errors
11 ' these exercise corner cases in the code
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
99 ' syntax error
100 a = INPUT(1)
110 ' illegal function call
120 CHAIN "test" ,,DELETE 60000-61000
130 ' type mismatch
140 LINE INPUT A
999 close:end
1000 print#1, err, erl
1010 resume next
2000 return

