10 REM PC-BASIC test 
20 REM PLAY syntax
35 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 ON ERROR GOTO 1000
45 SOUND OFF
50 PLAY
60 PLAY 10
70 PLAY "t255a"
75 PLAY "a", "b",
80 PLAY "a", "b"
90 PLAY "a", "b", "c"
95 PLAY "a", "b", "c",
100 PLAY "a", "b", "c", "d"
105 PLAY "a", "b", "c", "d",
110 PLAY "V0a"
120 PLAY "V-1a"
130 PLAY "V16a"
132 PLAY "V15a"
140 PLAY "V32768a"
200 SOUND ON
250 PLAY
260 PLAY 10
270 PLAY "t255a"
275 PLAY "a", "b",
280 PLAY "a", "b"
290 PLAY "a", "b", "c"
295 PLAY "a", "b", "c",
300 PLAY "a", "b", "c", "d"
305 PLAY "a", "b", "c", "d",
310 PLAY "V0a"
320 PLAY "V-1a"
330 PLAY "V16a"
332 PLAY "V15a"
340 PLAY "V32768a"
999 END
1000 PRINT#1, ERR, ERL
1010 RESUME NEXT
