5 ' test syntax error in FN
7 open "output.txt" for output as 1
10 on error goto 1000
20 ' this is a syntax error; when does it get triggered?
30 DEF FNB(X) = FNA(X) + PRINT
35 print#1, "hi!"
40 PRINT#1, FNB(X)
45 print#1, "bye!"
999 end
1000 print#1, err, erl
1010 resume next

