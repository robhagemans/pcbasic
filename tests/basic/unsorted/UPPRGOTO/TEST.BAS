5 open "output.txt" for output as 1
10 on error goto 100
20 go to 30
30 go  to 40
40 GO TO 50
50 GO  TO 60
60 GO SUB 1000
70 GO  SUB 1000
80 go sub 1000
90 go  sub 1000
95 print #1, "end"
99 END
100 print#1, "error", err, erl
110 resume next
1000 print#1, "subroutine"
1010 return
