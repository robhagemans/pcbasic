10 ' test various forms of number strings with VAL
20 open "output.txt" for output as 1
25 ' integer
30 print#1, VAL("1")
31 print#1, VAL("001")
35 ' single
40 print#1, VAL("1.2")
41 print#1, VAL(".2")
42 print#1, VAL("0.2")
43 print#1, VAL("2.")
45 ' single with exponent
50 print#1, VAL("1.2e23")
55 ' double with exponent
60 print#1, VAL("1.2d23")
65 ' hex
70 print#1, VAL("&hab56")
72 print#1, VAL("&H10")
75 'oct
80 print#1, VAL("&o70")
82 print#1, VAL("&17")
83 print#1, VAL("&O17")
90 close

