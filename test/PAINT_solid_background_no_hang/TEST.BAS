1 ' test for bug https://github.com/robhagemans/pcbasic/issues/120
2 ' a successful test finishes
3 ' bug behaviour is to hang on the flood fill
5 ' test case provided by mrclay
10 SCREEN 1:CLS
20 CIRCLE(15,15),4,1
30 PSET(16,16),1
40 PAINT(13,14),3,1
50 LOCATE 5: PRINT "You should see 'PASS!'"
60 'LOCATE 6: INPUT "after hitting Enter...", F
70 PAINT(13,14),0,1
80 PRINT "PASS!"

