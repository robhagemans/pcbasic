1 ' test reading the keyboard ring buffer
5 open "output.txt" for output as 1
10 DEF SEG=0
20 FOR I= 30 TO 66
30 PRINT#1, PEEK(I+1020);
35 NEXT:PRINT

