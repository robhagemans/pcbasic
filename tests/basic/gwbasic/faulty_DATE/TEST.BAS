10 ' test incorrect DATE formats
15 open "errors.txt" for output as 2
17 open "output.txt" for output as 1
20 on error goto 1000
25 date$="01-01-1981"
30 date$="aa-bb-cc":print#1, date$
40 date$="13-31-80":print#1, date$
50 date$="12-32-80":print#1, date$
52 date$="01-01-76":print#1, date$
55 date$="01-01-77":print#1, date$
60 date$="01-01-78":print#1, date$
65 date$="01-01-79":print#1, date$
70 date$="01-01-100":print#1, date$
75 date$="01-01-1979":print#1, date$
77 date$="01-01-1980":print#1, date$
80 date$="01-01-2099":print#1, date$
90 date$="01-01-2100":print#1, date$
100 date$="01-01-20100":print#1, date$
110 date$="02-30-2000":print#1, date$
999 end
1000 print#2, err, erl
1010 resume next

