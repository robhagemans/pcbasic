1 REM Music queue test with NOISE statement
2 OPEN "O", #1, "OUTPUT.TXT"
5 SOUND ON
6 A=TIMER
10 FOR I=1 TO 34:NOISE 0,15,18.2:NEXT
20 PRINT#1, USING "###"; 8*(TIMER-A)
30 SOUND 0,0

