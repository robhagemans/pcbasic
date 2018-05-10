1 REM Multivoice sound and foreground queue
4 OPEN "o", 1, "OUTPUT.TXT"
5 SOUND ON:A=TIMER
6 PLAY "t60
10 PLAY "mbcde", "", ""
20 SOUND 800,25,15,2
25 PLAY "mf"
30 PRINT#1, USING "###"; 8*(TIMER-A)

