1 ' test temporary string memory management
5 OPEN"output.txt" FOR OUTPUT AS 1
10 A$="12345"
15 PRINT#1, FRE(0)
20 PRINT#1, LEN(A$+"1")
25 PRINT#1, FRE(0)
30 PRINT#1, LEN(A$+"1")
35 PRINT#1, FRE(0)
40 PRINT#1, LEN(A$+"1"), LEN(A$+"123")
45 PRINT#1, FRE(0)
50 PRINT#1, LEN(A$+"1"+A$+"123")
55 PRINT#1, FRE(0)

