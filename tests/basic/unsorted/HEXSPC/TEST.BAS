10 REM PC-BASIC test: no space before hex token 
20 OPEN "output.txt" FOR OUTPUT AS 1
30 FOR I=1TO&HA
40 PRINT#1, I
50 NEXT
60 CLOSE

