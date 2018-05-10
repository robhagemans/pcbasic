1 REM are pauses treated as fully filled on gw but as notes on tandy?
2 open "o", #1, "output.txt"
5 PLAY "t60"
10 A=TIMER:PLAY "mfmlp4p4p4p4p4":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
20 A=TIMER:PLAY "mfmnp4p4p4p4p4":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
30 A=TIMER:PLAY "mfmsp4p4p4p4p4":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
40 A=TIMER:PLAY "mbmlp4p4p4p4p4":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
50 A=TIMER:PLAY "mbmnp4p4p4p4p4":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)
60 A=TIMER:PLAY "mbmsp4p4p4p4p4":PRINT#1, using "###"; 8*(TIMER-A);:print#1, PLAY(0)

