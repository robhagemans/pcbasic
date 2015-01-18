# -*- mode: python -*-
a = Analysis(['pcbasic'],
         pathex=['/Users/rob/pc-basic'],
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
      console=False )
coll = COLLECT(exe,
           a.binaries - [
                # exclude Scrap module as it leads to strange errors.
                ('pygame.scrap', None, None)
                ],
           a.zipfiles,
           a.datas,
           Tree('font', prefix='font'),
           Tree('encoding', prefix='encoding'),
           Tree('info', prefix='info'),
           strip=None,
           upx=True,
           name='pcbasic')
app = BUNDLE(coll,
         name='pcbasic.app',
         icon='/Users/rob/pc-basic/resources/pcbasic.icns')

