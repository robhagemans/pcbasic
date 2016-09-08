10 OPEN "data.dat" FOR OUTPUT AS 1
15 ON ERROR GOTO 1000
20 DATA 1,    2,4,5,   dfg hhj  rr , :
22 DATA 1,    2,4,5,   dfg "hhj  rr" , ":"
28 DATA ab, ab ," ab ", ab "cd", ab   "cd  ", ab"  cd", "ab,cd", "ab: DATA cd", 12, 3.4, 
29 DATA
30 DATA "1,    2,4",5, ""  dfg "hhj  rr" , ":"
35 READ A$: PRINT#1, I, "%"+A$+"%":GOTO 30
40 CLOSE
1000 PRINT#1, "error", ERR, ERL
1004 PRINT ERR,  ERL
1005 IF ERR=4 OR ERR=2 THEN END
1010 RESUME NEXT

