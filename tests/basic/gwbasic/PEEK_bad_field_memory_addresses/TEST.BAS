5 ' dump file memory for first file
10 OPEN "output.txt" FOR OUTPUT AS 2
30 PRINT#2, "addresses in first field but no field defined"
40 FOR I = 0 TO 127
50 PRINT#2, PEEK(3751+6+188+I); "  ";
60 NEXT
70 PRINT#2,
80 PRINT#2, "addresses in first file memory outside of field"
100 FOR I = 0 TO 6+188
110 PRINT#2, PEEK(3751+I); "  ";
120 NEXT
130 CLOSE

