# Imports para garantir que o PyInstaller encontre os módulos
from . import comandos
from . import folha_de_ponto
from . import interface
from . import services
from . import utils


__all__ = [
    'comandos',
    'folha_de_ponto', 
    'interface',
    'services',
    'utils',

]