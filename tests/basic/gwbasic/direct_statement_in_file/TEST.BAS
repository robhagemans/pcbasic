10 ' test direct statement in file 
25 width 40: key off
20 open "errors.txt" for output as 1
30 on error goto 100
40 load "direct"
50 end
100 print#1, err, erl
110 resume next

