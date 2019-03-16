10 OPEN "data.dat" FOR OUTPUT AS 1
20 DATA 1,    2,4,5,   dfg hhj  rr , :
30 FOR I=1 TO 10: READ A$: PRINT#1, I, "%"+A$+"%":NEXT
40 CLOSE

