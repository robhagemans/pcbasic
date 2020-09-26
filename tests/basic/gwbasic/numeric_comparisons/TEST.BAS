10 ' test numeric comparisons
20 ONE% = 1: ONE! = 1: ONE# = 1
30 TWO% = 2: TWO! = 2: TWO# = 2
40 open "output.txt" for output as 1
45 ?#1, ONE% = ONE%, ONE! = ONE!, ONE# = ONE#
50 ?#1, ONE% = ONE!, ONE! = ONE%
60 ?#1, ONE% = ONE#, ONE# = ONE%
70 ?#1, ONE# = ONE!, ONE! = ONE#
75 ?#1, ONE% = TWO%, ONE! = TWO!, ONE# = TWO#
80 ?#1, ONE% = TWO!, ONE! = TWO%
85 ?#1, ONE% = TWO#, ONE# = TWO%
90 ?#1, ONE# = TWO!, ONE! = TWO#
145 ?#1, ONE% >= ONE%, ONE! >= ONE!, ONE# >= ONE#
150 ?#1, ONE% >= ONE!, ONE! >= ONE%
160 ?#1, ONE% >= ONE#, ONE# >= ONE%
170 ?#1, ONE# >= ONE!, ONE! >= ONE#
175 ?#1, ONE% >= TWO%, ONE! >= TWO!, ONE# >= TWO#
180 ?#1, ONE% >= TWO!, ONE! >= TWO%
185 ?#1, ONE% >= TWO#, ONE# >= TWO%
190 ?#1, ONE# >= TWO!, ONE! >= TWO#
245 ?#1, ONE% <= ONE%, ONE! <= ONE!, ONE# <= ONE#
250 ?#1, ONE% <= ONE!, ONE! <= ONE%
260 ?#1, ONE% <= ONE#, ONE# <= ONE%
270 ?#1, ONE# <= ONE!, ONE! <= ONE#
275 ?#1, ONE% <= TWO%, ONE! <= TWO!, ONE# <= TWO#
280 ?#1, ONE% <= TWO!, ONE! <= TWO%
285 ?#1, ONE% <= TWO#, ONE# <= TWO%
290 ?#1, ONE# <= TWO!, ONE! <= TWO#
345 ?#1, ONE% > ONE%, ONE! > ONE!, ONE# > ONE#
350 ?#1, ONE% > ONE!, ONE! > ONE%
360 ?#1, ONE% > ONE#, ONE# > ONE%
370 ?#1, ONE# > ONE!, ONE! > ONE#
375 ?#1, ONE% > TWO%, ONE! > TWO!, ONE# > TWO#
380 ?#1, ONE% > TWO!, ONE! > TWO%
385 ?#1, ONE% > TWO#, ONE# > TWO%
390 ?#1, ONE# > TWO!, ONE! > TWO#
445 ?#1, ONE% < ONE%, ONE! < ONE!, ONE# < ONE#
450 ?#1, ONE% < ONE!, ONE! < ONE%
460 ?#1, ONE% < ONE#, ONE# < ONE%
470 ?#1, ONE# < ONE!, ONE! < ONE#
475 ?#1, ONE% < TWO%, ONE! < TWO!, ONE# < TWO#
480 ?#1, ONE% < TWO!, ONE! < TWO%
485 ?#1, ONE% < TWO#, ONE# < TWO%
490 ?#1, ONE# < TWO!, ONE! < TWO#
545 ?#1, ONE% <> ONE%, ONE! <> ONE!, ONE# <> ONE#
550 ?#1, ONE% <> ONE!, ONE! <> ONE%
560 ?#1, ONE% <> ONE#, ONE# <> ONE%
570 ?#1, ONE# <> ONE!, ONE! <> ONE#
575 ?#1, ONE% <> TWO%, ONE! <> TWO!, ONE# <> TWO#
580 ?#1, ONE% <> TWO!, ONE! <> TWO%
585 ?#1, ONE% <> TWO#, ONE# <> TWO%
590 ?#1, ONE# <> TWO!, ONE! <> TWO#
1000 close

