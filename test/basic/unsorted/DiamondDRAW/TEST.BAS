10 REM PC-BASIC test 
20 REM Draw a diamond and end up back where we started (issue #93)
30 SCREEN 1
40 DRAW "bm100,100s5f19g19h19e19"
50 OPEN "output.txt" FOR OUTPUT AS 1
60 PRINT#1, POINT(0), POINT(1)
70 CLOSE

