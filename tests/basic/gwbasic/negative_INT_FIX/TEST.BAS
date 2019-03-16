10 REM test INT and FIX on positive and negative values
20 open "output.txt" for output as 1
30 print#1, int(0.), fix(0.)
40 print#1, int(-0.5), fix(-0.5)
50 print#1, int(-1.), fix(-1.)
60 print#1, int(-1.5), fix(-1.5)
140 print#1, int(0.5), fix(0.5)
150 print#1, int(1.), fix(1.)
160 print#1, int(1.5), fix(1.5)
240 print#1, int(0.5#), fix(0.5#)
250 print#1, int(1#), fix(1#)
260 print#1, int(1.5#), fix(1.5#)
340 print#1, int(-0.5#), fix(-0.5#)
350 print#1, int(-1#), fix(-1#)
360 print#1, int(-1.5#), fix(-1.5#)
999 CLOSE
