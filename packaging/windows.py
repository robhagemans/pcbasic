"""
PC-BASIC - packaging.windows
Windows packaging

(c) 2015--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import distutils
import msilib

import cx_Freeze
from cx_Freeze import Executable

from .common import wash, _build_icon, _build_manifest, _prune, _remove, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG


def package(SETUP_OPTIONS, NAME, AUTHOR, VERSION, SHORT_VERSION, COPYRIGHT):
    """Build a Windows MSI package."""


    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            _build_icon()
            # only include 32-bit DLLs
            _build_manifest(INCLUDE_FILES + ('pcbasic/lib/win32_x86/*',), EXCLUDE_FILES)
            cx_Freeze.build_exe.run(self)
            build_dir = 'build/exe.{}/'.format(PLATFORM_TAG)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, dirs, files in os.walk(build_dir + 'lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for f in files:
                    name = os.path.join(root, f)
                    if (
                            # remove superfluous copies of python27.dll in lib/
                            # as there is a copy in the package root already
                            f.lower() == 'python27.dll' or f.lower() == 'msvcr90.dll'
                            # remove tests and examples
                            or testing
                            # we're only producing packages for win32_x86
                            or 'win32_x64' in name or name.endswith('.dylib')
                        ):
                        _remove(name)
            # remove lib dir altogether to avoid it getting copied into the msi
            # as everything in there is copied once already
            _prune('build/lib')
            # remove c++ runtime etc
            _remove(build_dir + 'msvcm90.dll')
            _remove(build_dir + 'msvcp90.dll')
            # remove modules that can be left out
            for module in ('distutils', 'setuptools', 'pydoc_data'):
                _prune(build_dir + 'lib/%s' % module)


    class BdistMsiCommand(cx_Freeze.bdist_msi):
        """Custom bdist_msi command."""

        def run(self):
            """Run build_msi command."""
            name = '{}-{}'.format(NAME, VERSION)
            _remove('dist/{}.msi'.format(name))
            cx_Freeze.bdist_msi.run(self)
            # close the database file so we can rename the file
            del self.db
            os.rename('dist/{}-win32.msi'.format(name), 'dist/{}.msi'.format(name))
            wash()

        def add_config(self, fullname):
            """Override cx_Freeze add_config."""
            # mostly copy-paste from cxfreeze source, wich some changes
            if self.directories:
                msilib.add_data(self.db, "Directory", self.directories)
            msilib.add_data(
                self.db, 'CustomAction',
                [("A_SET_TARGET_DIR", 256 + 51, "TARGETDIR", self.initial_target_dir)]
            )
            if self.add_to_path:
                msilib.add_data(
                self.db, 'Environment', [("E_PATH", "=-*Path", r"[~];[TARGETDIR]", "TARGETDIR")]
                )
            msilib.add_data(
                self.db, 'InstallUISequence', [
                    ("PrepareDlg", None, 140),
                    # this is new
                    # sould probably be conditional on "not already installed" or smth
                    ("WhichUsersDlg", "not Installed", 400),
                    ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                    ("SelectDirectoryDlg", "not Installed", 1230),
                    ("MaintenanceTypeDlg", "Installed and not Resume and not Preselected", 1250),
                    ("ProgressDlg", None, 1280),

            ])
            msilib.add_data(
                self.db, 'InstallExecuteSequence', [
                    ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                    ('WriteEnvironmentStrings', 'MSIINSTALLPERUSER=""', 5200),
                ]
            )
            for index, executable in enumerate(self.distribution.executables):
                if executable.shortcutName is not None and executable.shortcutDir is not None:
                    baseName = os.path.basename(executable.targetName)
                    msilib.add_data(
                        self.db, "Shortcut", [(
                            "S_APP_%s" % index, executable.shortcutDir, executable.shortcutName,
                            "TARGETDIR", "[TARGETDIR]%s" % baseName,
                            None, None, None, None, None, None, None
                        )]
                    )
            for tableName, data in self.data.items():
                msilib.add_data(self.db, tableName, data)

        def add_properties(self):
            """Override cx_Freeze add_properties."""
            # mostly copy-paste from cxfreeze
            metadata = self.distribution.metadata
            props = [
                ('DistVersion', metadata.get_version()),
                ('DefaultUIFont', 'DlgFont8'),
                ('ErrorDialog', 'ErrorDlg'),
                ('Progress1', 'Install'),
                ('Progress2', 'installs'),
                ('MaintenanceForm_Action', 'Repair'),
                ('ALLUSERS', '2'),
                ('MSIINSTALLPERUSER', '1'),
            ]
            email = metadata.author_email or metadata.maintainer_email
            if email:
                props.append(("ARPCONTACT", email))
            if metadata.url:
                props.append(("ARPURLINFOABOUT", metadata.url))
            if self.upgrade_code is not None:
                props.append(("UpgradeCode", self.upgrade_code))
            msilib.add_data(self.db, 'Property', props)

        def _add_whichusers_dialog(self):
            """Per-user or per-machine install dialog."""
            # based on dialog from cpython 2.7 source code
            # https://svn.python.org/projects/python/trunk/Tools/msi/msi.py
            whichusers = distutils.command.bdist_msi.PyDialog(
                self.db, "WhichUsersDlg", self.x, self.y, self.width, self.height,
                self.modal, self.title, "AdminInstall", "Next", "Cancel"
            )
            whichusers.title(
                "Select whether to install [ProductName] for all users of this computer."
            )
            # A radio group with two options: allusers, justme
            g = whichusers.radiogroup(
                "AdminInstall", 135, 60, 235, 80, 3, "WhichUsers", "", "Next"
            )
            g.condition("Disable", "VersionNT=600") # Not available on Vista and Windows 2008
            g.add("ALL", 0, 5, 150, 20, "Install for all users")
            g.add("JUSTME", 0, 25, 235, 20, "Install just for me")

            whichusers.back("Back", None, active=0)

            c = whichusers.next("Next >", "Cancel")
            # SetProperty events
            # https://docs.microsoft.com/en-us/windows/desktop/Msi/setproperty-controlevent
            c.event("[MSIINSTALLPERUSER]", "{}", 'WhichUsers="ALL"', 1)
            c.event("[MSIINSTALLPERUSER]", "1", 'WhichUsers="JUSTME"', 1)
            # set the target dir to the default location for per-user/per-machine installs
            c.event("[TARGETDIR]", "[ProgramFilesFolder]\\%s %s" % (NAME, SHORT_VERSION), 'WhichUsers="JUSTME"', 1)
            c.event("EndDialog", "Return", 3)

            c = whichusers.cancel("Cancel", "AdminInstall")
            c.event("SpawnDialog", "CancelDlg")

        def add_ui(self):
            self._add_whichusers_dialog()
            cx_Freeze.bdist_msi.add_ui(self)


    # remove the WriteEnvironmentStrings action from the default list
    # since cx_Freeze picks up the default list and puts it into the MSI
    # but we can't have environment changes for per-user installs (?)
    sequence = msilib.sequence.InstallExecuteSequence
    for index, info in enumerate(sequence):
        if info[0] == u'WriteEnvironmentStrings':
            break
    else:
        raise 0
    env_sequence = sequence[index]
    del sequence[index]

    # setup commands
    SETUP_OPTIONS['cmdclass'] = dict(
        build_exe=BuildExeCommand,
        bdist_msi=BdistMsiCommand,
        **COMMANDS
    )

    numversion = '.'.join(v for v in VERSION.encode('ascii').split('.') if v.isdigit())

    UPGRADE_CODE = '{714d23a9-aa94-4b17-87a5-90e72d0c5b8f}'
    PRODUCT_CODE = msilib.gen_uuid()

    # these must be bytes for cx_Freeze bdist_msi
    SETUP_OPTIONS['name'] = NAME.encode('ascii')
    SETUP_OPTIONS['author'] = AUTHOR.encode('ascii')
    SETUP_OPTIONS['version'] = numversion

    # compile separately, as they end up in the wrong place anyway
    SETUP_OPTIONS['ext_modules'] = []

    # gui launcher
    SETUP_OPTIONS['entry_points']['gui_scripts'] = ['pcbasicw=pcbasic:main']

    directory_table = [
        (
            'StartMenuFolder',
            'TARGETDIR',
            '.',
        ),
        (
            'MyProgramMenu',
            'StartMenuFolder',
            'PCBASI~1|PC-BASIC 2.0',
        ),
    ]
    # https://stackoverflow.com/questions/15734703/use-cx-freeze-to-create-an-msi-that-adds-a-shortcut-to-the-desktop#15736406
    shortcut_table = [
        (
            'ProgramShortcut',        # Shortcut
            'MyProgramMenu',          # Directory_
            'PC-BASIC %s' % VERSION,  # Name
            'TARGETDIR',              # Component_
            '[TARGETDIR]pcbasicw.exe',# Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            # PersonalFolder is My Documents, use as Start In folder
            'PersonalFolder'          # WkDir
        ),
        (
            'DocShortcut',            # Shortcut
            'MyProgramMenu',          # Directory_
            'Documentation',          # Name
            'TARGETDIR',              # Component_
            '[TARGETDIR]PC-BASIC_documentation.html',# Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            'TARGETDIR'               # WkDir
        ),
        (
            'UninstallShortcut',      # Shortcut
            'MyProgramMenu',          # Directory_
            'Uninstall',              # Name
            'TARGETDIR',              # Component_
            '[SystemFolder]msiexec.exe', # Target
            '/x %s' % PRODUCT_CODE,           # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            # PersonalFolder is My Documents, use as Start In folder
            'TARGETDIR'               # WkDir
        ),
    ]
    msi_data = {
        'Directory': directory_table,
        'Shortcut': shortcut_table,
        'Icon': [('PC-BASIC-Icon', msilib.Binary('resources/pcbasic.ico')),],
        'Property': [('ARPPRODUCTICON', 'PC-BASIC-Icon'),],
    }

    # cx_Freeze options
    SETUP_OPTIONS['options'] = {
        'build_exe': {
            'packages': ['pkg_resources._vendor'],
            'excludes': [
                'Tkinter', '_tkinter', 'PIL', 'PyQt4', 'scipy', 'pygame',
                'pywin', 'win32com', 'test',
            ],
            'include_files': ['doc/PC-BASIC_documentation.html'],
            'include_msvcr': True,
            #'optimize': 2,
        },
        'bdist_msi': {
            'data': msi_data,
            # add console entry points to PATH
            'add_to_path': True,
            # enforce removal of old versions
            'upgrade_code': UPGRADE_CODE,
            'product_code': PRODUCT_CODE,
            'initial_target_dir': 'c:\\Program Files\\%s %s' % (NAME, SHORT_VERSION),
        },
    }

    SETUP_OPTIONS['executables'] = [
        Executable(
            'pc-basic', base='Console', targetName='pcbasic.exe', icon='resources/pcbasic.ico',
            copyright=COPYRIGHT),
        Executable(
            'pc-basic', base='Win32GUI', targetName='pcbasicw.exe', icon='resources/pcbasic.ico',
            #shortcutName='PC-BASIC %s' % VERSION, shortcutDir='MyProgramMenu',
            copyright=COPYRIGHT),
    ]

    # call cx_Freeze's setup() with command bdist_msi
    cx_Freeze.setup(script_args=['bdist_msi'], **SETUP_OPTIONS)
