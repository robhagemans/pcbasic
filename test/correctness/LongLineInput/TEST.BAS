10 REM PC-BASIC test 
20 REM LINE INPUT on long lines
30 open "input.txt" for input as 1
40 open "output.txt" for output as 2
45 WHILE NOT EOF(1)
50 LINE INPUT#1, a$
60 WRITE#2, a$
70 WEND
80 CLOSE

