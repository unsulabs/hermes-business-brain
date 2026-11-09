"""Zero-dependency diagnostic. Must work even if PyYAML/jsonschema are NOT installed."""
from __future__ import annotations

import os
import platform
import shutil
import sys
from importlib import util
from pathlib import Path


def diagnose(vault=None):
    cli=shutil.which('obsidian')
    candidates=[]
    if sys.platform=='darwin':
        candidates=[Path('/Applications/Obsidian.app'),Path.home()/'Applications'/'Obsidian.app']
    elif sys.platform=='win32':
        candidates=[Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Obsidian/Obsidian.exe']
    else:
        candidates=[Path('/usr/bin/obsidian'),Path('/opt/Obsidian/obsidian')]
    modules={name:'INSTALLED' if util.find_spec(name) else 'NOT INSTALLED' for name in ('yaml','jsonschema')}
    result={'producto':'Business Brain 0.2.0',
            'so':platform.platform(), 'python':sys.version.split()[0], 'recomendado_python':'3.11+',
            'directorio_trabajo':str(Path.cwd()),'dependencias_python':modules,
            'obsidian_ruta_cli':cli,'candidatos_obsidian':[str(p) for p in candidates if p.exists()],
            'obsidian_version':'NOT VERIFIED', 'obsidian_gui':'NOT VERIFIED',
            'bases':'NOT VERIFIED','templates':'NOT VERIFIED',
            'acceso_a_archivos_empresariales':'NOT VERIFIED',
            'instalacion_real':'NOT DONE BY THIS COMMAND',
            'siguiente':'Request installation and path authorization before any write'}
    if vault is not None:
        p=Path(vault).expanduser().resolve()
        result['boveda_solicitada']=str(p)
        result['config_empresa_existe']=(p/'90_Sistema/config_empresa.yaml').is_file()
        result['nota']='Config file existence does not demonstrate integrity/identity; run validate after installing dependencies'
    return result
