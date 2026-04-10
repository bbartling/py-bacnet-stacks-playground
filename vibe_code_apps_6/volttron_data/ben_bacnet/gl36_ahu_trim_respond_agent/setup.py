from os import path
from setuptools import setup, find_packages

MAIN_MODULE = 'agent'
packages = find_packages('.')
agent_package = ''
for package in packages:
    if path.isfile(package + '/' + MAIN_MODULE + '.py'):
        agent_package = package
        break
if not agent_package:
    raise RuntimeError('No agent package found')
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

setup(
    name=agent_package + 'agent',
    version=__version__,
    install_requires=['volttron'],
    packages=packages,
    entry_points={'setuptools.installation': ['eggsecutable = ' + agent_module + ':main']}
)
