1 ' test INPUT$ in FN: when do we wait?
10 DEF FNA(X) = VAL(INPUT$(2)) + X
15 open "output.txt" for output as 1
20 PRINT#1, FNA(X) + FNA(-42)
30 close

