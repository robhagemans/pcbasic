5 ' test DRAW with numeric variables inlined
10 screen 1
20 v%=5
30 v!=5
40 v#=5
50 v$="5"
60 on error goto 1000
70 open "errors.txt" for output as 1
100 ' numeric variable inline
105 DRAW "F=v%;"
110 DRAW "L=v!;"
120 DRAW "E=v#;"
130 DRAW "G=v$;" ' type mismatch
999 end
1000 print#1, err, erl
1010 resume next

