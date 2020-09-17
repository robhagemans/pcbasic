10 'test using KILL with long filenames
20 open "output.txt" for output as 1
30 open "errors.txt" for output as 2
40 on error goto 1000
50 kill "VERYLONG.EXT"
60 kill "VERYLONGFILENAME.EXT"
70 kill "VERYLONG.EXT"
80 kill "veryLongFilename.ext"
999 close: end
1000 print#2, err, erl
1010 resume next

