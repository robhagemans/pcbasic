basedir='../..'
# -*- mode: python -*-
a = Analysis([basedir+'/run.py'],
         pathex=[basedir],
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
      console=False)
coll = COLLECT(exe,
           a.binaries - [
                # exclude Scrap module as it leads to strange errors.
                ('pygame.scrap', None, None)
                ],
           a.zipfiles,
           a.datas,
           Tree(basedir+'/pcbasic/font', prefix='font'),
           Tree(basedir+'/pcbasic/codepage', prefix='codepage'),
           Tree(basedir+'/pcbasic/data', prefix='data'),
           Tree(basedir+'/doc', prefix='doc'),
           strip=None,
           upx=True,
           name='pcbasic')
app = BUNDLE(coll,
         name='PC-BASIC.app',
         icon='pcbasic.icns')
