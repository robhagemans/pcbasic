5 ' POKE into field memory for unopened file
6 ' does not test, just exercise
30 PRINT "addresses in first field but no field defined"
40 FOR I = 0 TO 127
50 POKE 3751+6+188+I,0
60 NEXT
80 PRINT "addresses in first file memory outside of field"
100 FOR I = 0 TO 6+188
110 POKE 3751+I,0
120 NEXT

