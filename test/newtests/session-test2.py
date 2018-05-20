import pcbasic
import random


with pcbasic.Session(extension=random) as s:
    s.execute('a=1')
    print s.evaluate('string$(a+2, "@")')
    s.set_variable('B$', 'abcd')
    s.execute('''
        10 a=5
        20 print a
        run
        _seed(42)
        b = _uniform(a, 25.6)
        print a, b
    ''')
