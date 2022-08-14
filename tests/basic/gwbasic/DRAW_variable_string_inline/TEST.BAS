5 ' test DRAW with string variables inlined
10 screen 1
20 v%=5
30 v!=5
40 v#=5
50 v$="D5"
60 on error goto 1000
70 open "errors.txt" for output as 1
100 ' string variable inline
105 DRAW "Xv%;" ' type mismatch
110 DRAW "Xv!;" ' type mismatch
120 DRAW "Xv#;" ' type mismatch
130 DRAW "Xv$;"
999 end
1000 print#1, err, erl
1010 resume next

