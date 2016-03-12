10 REM PC-BASIC test
20 OPEN "output.txt" FOR OUTPUT AS 1
25 ON ERROR GOTO 1000
100 PRINT#1, USING "#.####"; ABS(1.5#)
110 PRINT#1, USING "#.####"; ATN(1.5#)
120 PRINT#1, USING "#.####"; COS(1.5#)
130 PRINT#1, USING "#.####"; EXP(1.5#)
140 PRINT#1, USING "#.####"; FIX(1.5#)
150 PRINT#1, USING "#.####"; INT(1.5#)
160 PRINT#1, USING "#.####"; LOG(1.5#)
170 PRINT#1, USING "#.####"; SGN(1.5#)
180 PRINT#1, USING "#.####"; SIN(1.5#)
190 PRINT#1, USING "#.####"; SQR(1.5#)
195 PRINT#1, USING "#.####"; TAN(1.5#)
200 PRINT#1, USING "#.####"; ABS(1.5)
210 PRINT#1, USING "#.####"; ATN(1.5)
220 PRINT#1, USING "#.####"; COS(1.5)
230 PRINT#1, USING "#.####"; EXP(1.5)
240 PRINT#1, USING "#.####"; FIX(1.5)
250 PRINT#1, USING "#.####"; INT(1.5)
260 PRINT#1, USING "#.####"; LOG(1.5)
270 PRINT#1, USING "#.####"; SGN(1.5)
280 PRINT#1, USING "#.####"; SIN(1.5)
290 PRINT#1, USING "#.####"; SQR(1.5)
295 PRINT#1, USING "#.####"; TAN(1.5)
900 CLOSE
910 END
1000 PRINT#1, USING "#.####"; "Error:", ERR, ERL
1010 RESUME NEXT
