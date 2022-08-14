5 ' test DRAW with string variables as pointer reference
10 screen 1
20 v%=5
30 v!=5
40 v#=5
50 v$="D5"
60 on error goto 1000
70 open "errors.txt" for output as 1
200 ' string variable with varptr$
205 DRAW "X=" + VARPTR$(v%) ' type mismatch
210 DRAW "X=" + VARPTR$(v!) ' type mismatch
220 DRAW "X=" + VARPTR$(v#) ' type mismatch
230 DRAW "X=" + VARPTR$(v$)
999 end
1000 print#1, err, erl
1010 resume next

