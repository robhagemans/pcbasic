10 ' test MID$ with zero and negative number of characters
20 open "output.txt" for output as 1
30 on error goto 1000
40 a$="12345"
50 MID$(a$,1,0) = "": print#1, a$
60 MID$(a$,1,0) = "a": print#1, a$
70 MID$(a$,1,0) = "abc": print#1, a$
80 MID$(a$,1,-1) = "": print#1, a$
90 MID$(a$,1,-1) = "a": print#1, a$
999 end
1000 print#1, err, erl
1010 resume next

