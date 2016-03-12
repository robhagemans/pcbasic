5 OPEN "output" FOR OUTPUT AS 1
10 FOR I= 1 TO 25
20 A = RND:B=RND:C=RND:D=RND:E=RND
30 PRINT#1, A, B,C,D,E
40 PRINT#1, USING "#.#########";A;:PRINT#1,
50 PRINT#1, USING "#.#########";B;:PRINT#1,
60 PRINT#1, USING "#.#########";C;:PRINT#1,
70 PRINT#1, USING "#.#########";D;:PRINT#1,
75 PRINT#1, USING "#.#########";E;:PRINT#1,
80 NEXT
