1 open "output.txt" for output as 1
5 PLAY "t60"
10 A=TIMER:PLAY "mfmlcdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
20 A=TIMER:PLAY "mfmncdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
30 A=TIMER:PLAY "mfmscdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
50 A=TIMER:PLAY "mbmlcdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
60 A=TIMER:PLAY "mbmncdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
70 A=TIMER:PLAY "mbmscdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
100 play "t60"
150 A=TIMER:PLAY "mbmlcdefgcdefgcdefgcdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
160 A=TIMER:PLAY "mbmncdefgcdefgcdefgcdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
170 A=TIMER:PLAY "mbmscdefgcdefgcdefgcdefg":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)

