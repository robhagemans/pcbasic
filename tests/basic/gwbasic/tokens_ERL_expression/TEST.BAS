10 ' test tokenising ERL expressions
11 ' i.e. do the numbers in the expression get interpreted as line numbers?
20 ON ERROR GOTO 40
30 K
40 PRINT ERR, ERL
50 PRINT ERL+20
60 PRINT ERL=65000
70 PRINT X+65000!
75 PRINT (ERL+50)/2
77 PRINT (ERL+51)/2
79 PRINT 77+(ERL+51)/2-77

