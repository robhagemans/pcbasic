10 REM PC-BASIC test 
20 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
30 O$="0"                                                                       
40 ON VAL(O$) GOTO 100,200,300                                                  
50 PRINT#1, 1                                                                           
100 PRINT#1, 2                                                                   
200 PRINT#1, 3                                                                  
300 PRINT#1, 4
1000 CLOSE: END
