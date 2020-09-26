1 REM on tandy - line 10 takes 4 seconds and leaves 25 notes in buffer, line 20 takes 3.75 and leaves 26 notes
3 REM the reason seems to be a synch signal at the start of PLAY taking up a slot in the buffer
4 open "output.txt" for output as 1
5 play "t60"
10 A=TIMER:PLAY"mbms cdefg cdefg":PLAY"ml cdefg cdefg cdefg cdefg":PRINT#1, using "###"; TIMER-A;: print#1,, PLAY(0): SOUND 0,0
20 A=TIMER:PLAY"mbms cdefg cdefg       ml cdefg cdefg cdefg cdefg":PRINT#1, using "###"; TIMER-A;: print#1,, PLAY(0): SOUND 0,0

