10 ' exercise more PLAY mml 
20 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
30 ON ERROR GOTO 1000
35 PLAY "T255" ' make the test quicker
40 PLAY "N0" ' another way of getting a pause
50 PLAY "P" ' no length, ifc
60 PLAY ">>>>>>>C" ' ignore last, max 6th octave
70 PLAY "<<<<<<<C" 'ignore last, min 0th octave
80 PLAY "e#" ' ifc
90 PLAY "F-" ' ifc
100 PLAY "c#" ' ok
110 PLAY "D-" ' ok
120 PLAY "MZ" ' ifc
130 PLAY "l64;a;b" ' ok
140 play "l64;;a;b" ' ifc
999 END
1000 PRINT#1, ERR, ERL
1010 RESUME NEXT
