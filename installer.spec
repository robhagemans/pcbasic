# -*- mode: python -*-
a = Analysis(['pcbasic.py'],
             pathex=['/home/rob/Projects/basic-project/pc-basic'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='pcbasic',
          debug=False,
          strip=None,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               Tree('cpi', prefix='cpi'),
               [
                    ('INFO.BAS', '/home/rob/Projects/basic-project/pc-basic/INFO.BAS', 'DATA'),
                    ('ABOUT', '/home/rob/Projects/basic-project/pc-basic/ABOUT', 'DATA'),
                    ('GPL3', '/home/rob/Projects/basic-project/pc-basic/GPL3', 'DATA'),
                    ('HELP', '/home/rob/Projects/basic-project/pc-basic/HELP', 'DATA'),
                    ('CC-BY-SA', '/home/rob/Projects/basic-project/pc-basic/CC-BY-SA', 'DATA'),
                    ('COPYING', '/home/rob/Projects/basic-project/pc-basic/COPYING', 'DATA'),
               ],
               strip=None,
               upx=True,
               name='pcbasic')
