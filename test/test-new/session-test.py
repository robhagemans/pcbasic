import pcbasic
from pcbasic import Session

with Session(stdio=True) as s:
    s.execute('a=1')
    print s.evaluate('a+2')
    print s.evaluate('"abc"+"d"')
    print s.evaluate('string$(a+2, "@")')
    s.set_variable('B$', 'abcd')
    print s.get_variable('B$')
    print s.evaluate('LEN(B$)')
    print s.evaluate('C!')
    print s.get_variable('D%')
    print s.set_variable('A%()', [[0,0,5],[0,0,6]])
    print s.get_variable('A%()')
    print s.evaluate('A%(0,2)')
    print s.evaluate('A%(1,2)')
    print s.evaluate('A%(1,7)')
    print s.evaluate('FRE(0)')
    print s.evaluate('CSRLIN')
    s.execute('print b$')
    print s.evaluate('CSRLIN')


def add(x, y):
    print "add", repr(x), repr(y)
    return x+y

with Session(stdio=True, extension=__name__) as s:
    s.execute('''
        10 a=5
        20 print a
        run
        b = _add(a, 1)
        print a, b
    ''')
    s.execute('run')
    s.execute('? a')
    print s.get_variable("a")
    print


class ExtendedSession(Session):

    def __init__(self):
        Session.__init__(self, stdio=True, extension=self)

    def adda(self, x):
        print "adda", repr(x), repr(self.get_variable("a"))
        return x + self.get_variable("a")


with ExtendedSession() as s:
    s.execute('''
        a = 4
        b = _adda(1)
        print a, b
    ''')


