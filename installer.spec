import platform




if platform.system() == 'Windows':
    # -*- mode: python -*-
    a = Analysis(['pcbasic'],
                 pathex=['C:\\Documents and Settings\\rob\\My Documents\\Projects\\pc-basic_distributions\\pc-basic'],
                 hiddenimports=[],
                 hookspath=None,
                 runtime_hooks=None)
    pyz = PYZ(a.pure)
    exe = EXE(pyz,
              a.scripts,
              exclude_binaries=True,
              name='pcbasic.exe',
              debug=False,
              strip=None,
              upx=True,
              console=False , 
		  icon='C:\\Documents and Settings\\rob\\My Documents\\Projects\\pc-basic_distributions\\pc-basic\\resources\\pcbasic.ico')
    coll = COLLECT(exe,
                   a.binaries,
                   a.zipfiles,
                   a.datas,
                   Tree('font', prefix='font'),
                   Tree('encoding', prefix='encoding'),
                   Tree('info', prefix='info'),
                   strip=None,
                   upx=True,
                   name='pcbasic')


elif platform.system() == 'Linux':
    # -*- mode: python -*-
    a = Analysis(['pcbasic'],
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
                   a.binaries - [
                        ('libcrypto.so.1.0.0', None, None),
                        ('libfreetype.so.6', None, None),
                        ('libncursesw.so.5', None, None),
                        ('libsmpeg-0.4.so.0', None, None),
                        ('libsndfile.so.1', None, None), 
                        ('libvorbisenc.so.2', None, None),
                        ('libvorbis.so.0', None, None),
                        ('libvorbisfile.so.3', None, None),
                        ('libogg.so.0', None, None),
                        ('libpng12.so.0', None, None),
                        ('libmikmod.so.2', None, None),
                        ('libcaca.so.0', None, None),
                        ('libjpeg.so.8', None, None),
                        ('libFLAC.so.8', None, None),
                        ('libblas.so.3gf', None, None),
                        ('liblapack.so.3gf', None, None),
                        ('libgfortran.so.3', None, None),
                        ('libslang.so.2', None, None),
                        ('libtiff.so.4', None, None),
                        ('libquadmath.so.0', None, None),
                        ('libssl.so.1.0.0', None, None),
                        ('libbz2.so.1.0', None, None),
                        ('libdbus-1.so.3', None, None),
                        ('libstdc++.so.6', None, None),
                        ('libreadline.so.6', None, None), # though this may be useful in future for dumbterm mode 
                        ('libtinfo.so.5', None, None),
                        ('libexpat.so.1', None, None),
                        ('libmad.so.0', None, None),
                        ('libjson.so.0', None, None),
                        ('libgcc_s.so.1', None, None),
                        ('libasyncns.so.0', None, None),
                   ],
                   a.zipfiles,
                   a.datas,
                   Tree('font', prefix='font'),
                   Tree('encoding', prefix='encoding'),
                   Tree('info', prefix='info'),
                   strip=None,
                   upx=True,
                   name='pcbasic')
                   
                   
elif platform.system() == 'Darwin':
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
               a.binaries,
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

