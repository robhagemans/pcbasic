10 ' test incorrect TIME formats
15 open "errors.txt" for output as 2
20 on error goto 1000
30 time$="01:02:03:04"
40 time$="24:01:00"
50 time$="23:60:00"
60 time$="01:01:60"
999 end
1000 print#2, err, erl
1010 resume next

