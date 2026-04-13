from setuptools import find_packages, setup

MAIN_MODULE = 'agent'
packages = find_packages('.')
agent_package = 'oat_share_agent'
agent_module = agent_package + '.' + MAIN_MODULE
_temp = __import__(agent_module, globals(), locals(), ['__version__'], 0)
__version__ = _temp.__version__

setup(
    name=agent_package + 'agent',
    version=__version__,
    install_requires=['volttron'],
    packages=packages,
    include_package_data=True,
    entry_points={
        'setuptools.installation': [
            'eggsecutable = ' + agent_module + ':main',
        ]
    }
)
