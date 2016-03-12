5 A$="####."
6 A = 9.999999
8 OPEN "output" FOR OUTPUT AS 1
10 FOR I=1 TO 20
20 PRINT#1, I,
30 PRINT#1, USING A$;A
40 A$ = A$+"#"
50 NEXT

