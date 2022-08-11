10 REM length of the music queue - 32 legato notes or 16 normal/staccato notes
20 OPEN "o", 1, "output.txt"
100 play "t60"
150 A=TIMER:PLAY "mbml cdefgcdefg cdefgcdefg cdefgcdefg cdefg":PRINT#1, USING "###"; 8*(TIMER-A):PRINT#1,, PLAY(0):SOUND 0,0
160 A=TIMER:PLAY "mbmn cdefgcdefg cdefgcdefg":PRINT#1, USING "###"; 8*(TIMER-A):PRINT#1,, PLAY(0):SOUND 0,0
170 A=TIMER:PLAY "mbms cdefgcdefg cdefgcdefg":PRINT#1, USING "###"; 8*(TIMER-A):PRINT#1,, PLAY(0):SOUND 0,0

