10 ' test ON (event) GOSUB 0
11 ' and ON (even) GOSUB non-existing line number
20 open "output.txt" for output as 1
30 on error goto 1000
40 on timer(1) gosub 2000
60 on timer(1) gosub 0
70 on timer(1) gosub 65
999 close: end
1000 print#1, err, erl
1010 resume next
2000 print#1, "trigger", return

