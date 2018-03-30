10 A=TIMER
20 FOR I=1 TO 100000:NEXT
30 A = TIMER-A
40 REM 14.01 on intel atom: 6.4s for 10000
50 PRINT "100000 loops, float counter: "; USING "##.###"; A
110 A=TIMER
120 FOR J%=1 TO 10:FOR I%=1 TO 10000:NEXT:NEXT
130 A = TIMER-A
150 PRINT "100000 loops, int counter: "; USING "##.###"; A
210 A=TIMER
220 FOR I=1 TO 100000
225 NEXT
230 A = TIMER-A
250 PRINT "100000 loops (two-line), float counter: "; USING "##.###"; A
