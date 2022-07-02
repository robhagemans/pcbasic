1 ' test temporary string memory management
5 OPEN "output.txt" FOR OUTPUT AS 1
10 A$="12345"
15 PRINT#1, FRE(0)
20 FOR I = 1 TO LEN(A$+"1"): NEXT
25 PRINT#1, FRE(0)
30 A = LEN(A$+"1")
35 PRINT#1, FRE(A$+"1")
50 PRINT#1, (A$+"1"+A$+"123")
55 PRINT#1, FRE(0)

