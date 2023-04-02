3 ' test for curren tgraphics position with and without WINDOW
4 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
5 SCREEN 9
9 ' without WINDOW, the PSET position follows the DRAW position
10 GOSUB 100
19 ' with WINDOW SCREEN, it does not
20 WINDOW SCREEN (0,0)-(200,200)
30 GOSUB 100
39 ' with WINDOW alone, also not
40 WINDOW (0,0)-(200,200)
50 GOSUB 100
60 END
100 DRAW "c4l10": PRINT#1, POINT(0), POINT(1):PSET STEP(0,0),15:PRINT#1, POINT(0), POINT(1)
110 RETURN

