10 REM PC-BASIC test 
20 REM WIDTH syntax
30 open "output.txt" for output as 1
40 on error goto 10000
100 width "scr"+"n:", 80
110 print#1, 110
120 width 40 yada
130 print#1, "yada"
140 width "yada", 40
150 print #1, "yada"
160 width 40
170 width 40,
180 width 40, 25
190 width 40, 25,
200 width 40, 25, 1
210 width 40, 25, 1,
9999 end
10000 print#1, "error", err, erl
10010 resume next
