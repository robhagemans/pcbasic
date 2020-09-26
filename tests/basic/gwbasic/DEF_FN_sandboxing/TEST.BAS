5 REM test sandboxing of DEF FN parameters
5 Y=100 ' leave x unset
10 DEF FNA(X,Y) = X+Y
15 OPEN"OUTPUT.TXT" FOR OUTPUT AS 1
19 ' run the DEF FN using temporary variables X and Y
20 PRINT#1, FNA(1,2)
29 ' X and Y should retain their values X=0, Y=100
30 PRINT#1, X, Y
40 CLOSE 1

