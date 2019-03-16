5 ' test TIMER event
10 open "output.txt" for output as 1
20 S=TIMER
32 ON TIMER(1) GOSUB 100
34 TIMER ON
70 GOTO 70
100 PRINT#1, TIMER - S
110 END

