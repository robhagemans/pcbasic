5 ' test DRAW with numeric variables as pointer reference
10 screen 1
20 v%=5
30 v!=5
40 v#=5
50 v$="5"
60 on error goto 1000
70 open "errors.txt" for output as 1
200 ' numeric variable with varptr$
205 DRAW "F=" + VARPTR$(v%)
210 DRAW "L=" + VARPTR$(v!)
220 DRAW "E=" + VARPTR$(v#)
230 DRAW "G=" + VARPTR$(v$) ' type mismatch
999 end
1000 print#1, err, erl
1010 resume next

