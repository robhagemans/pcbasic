10 REM PRINT USING test 
20 OPEN "OUTPUT" FOR OUTPUT AS 1
25 ON ERROR GOTO 10000
29 REM syntax and literals
30 PRINT#1, USING "abc"; 1
40 PRINT#1, USING "abc #"; 1
50 PRINT#1, USING "abc # #"; 1, 2
60 PRINT#1, USING "abc # #"; 1; 2
70 PRINT#1, USING "abc #"; 1; 2
80 PRINT#1, USING "_# #"; 2
90 PRINT#1, USING " # "; 1,2,3,4,5
1000 REM strings
1010 PRINT#1, USING "!"; "abcde"
1020 PRINT#1, USING "\ \"; "abcde"
1030 PRINT#1, USING "&"; "abcde"
2000 REM numbers
2010 PRINT#1, USING "###"; 12, 123, 1234, 12345, -12345, -123, -12
2020 PRINT#1, USING "."; 0
2030 PRINT#1, USING "##,,#"; 1000, 11000, -1000
2040 PRINT#1, USING "+###"; 2000
2050 PRINT#1, USING "**##"; 1, 10, 100, 1000, 10000, -1, -10, -100, -1000, -10000
2060 PRINT#1, USING "$$##"; 1, 10, 100, 1000, 10000, -1, -10, -100, -1000, -10000
2070 PRINT#1, USING "###.###"; 1
2080 PRINT#1, USING "####+"; 1, -1
2090 PRINT#1, USING "####-"; 1, -1
2100 PRINT#1, USING "####^^^^"; 0, 1, 10, 100, 1000, 10000, 0.1, 0.01, 0.001
3000 REM double-precision numbers
3010 PRINT#1, USING "###"; 12#, 123#, 1234#, 12345#, -12345#, -123#, -12#
3020 PRINT#1, USING "."; 0#
3030 PRINT#1, USING "##,,#"; 1000#, 11000#, -1000#
3040 PRINT#1, USING "+###"; 2000#
3050 PRINT#1, USING "**##"; 1#, 10#, 100#, 1000#, 10000#, -1#, -10#, -100#, -1000#, -10000#
3060 PRINT#1, USING "$$##"; 1#, 10#, 100#, 1000#, 10000#, -1#, -10#, -100#, -1000#, -10000#
3070 PRINT#1, USING "###.###"; 1#
3080 PRINT#1, USING "####+"; 1#, -1#
3090 PRINT#1, USING "####-"; 1#, -1#
3100 PRINT#1, USING "####^^^^"; 0#, 1#, 10#, 100#, 1000#, 10000#, 0.1#, 0.01#, 0.001#
9999 CLOSE: END
10000 PRINT#1, "error:", ERR, ERL
10010 RESUME NEXT
