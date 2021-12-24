import os
from pathlib import Path

import versioningit

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

if True:
    # if installed editable
    pyprojectpath = Path(os.path.abspath(__file__)).parent.parent
    print(pyprojectpath)
    __version__ = versioningit.get_version(project_dir=pyprojectpath)
else:
    __version__ = version("qcodes")
