10 ' test INPUT# from a file with linefeeds and quotes 
20 open "input.txt" for input as 1
30 open "output.txt" for output as 2
40 input#1, a$: print#2, "--" a$ "--"
50 input#1, a$: print#2, "--" a$ "--"
60 close

