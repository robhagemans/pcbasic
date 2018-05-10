1 REM Music foreground test with SOUND statement
2 OPEN "O", #1, "OUTPUT.TXT"
5 PLAY "mf"
9 ' round duration to eigth of a second
10 A=TIMER:SOUND 800,18.2:SOUND 800,18.2:PRINT#1, USING "###"; 8*(TIMER-A)

