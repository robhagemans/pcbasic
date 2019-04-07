10 ' test incorrect expressions with math operators
20 open "output.txt" for output as 1
30 on error goto 1000
40 print#1, 1+"a"
45 print#1, "a"+1
50 print#1, 1-"a"
55 print#1, "a"-1
60 print#1, 1*"a"
65 print#1, "a"*1
70 print#1, 1/"a"
75 print#1, "a"/1
80 print#1, 1\"a"
85 print#1, "a"\1
90 print#1, 1^"a"
95 print#1, "a"^1
999 end
1000 print#1, err, erl
1010 resume next

