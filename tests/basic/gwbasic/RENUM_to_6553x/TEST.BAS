10 ' test RENUM to illegal line numbers 6553x
20 open "errors.txt" for output as 1
25 on error goto 100
30 renum 65520
40 end
100 print#1, err, erl
110 resume next

