"""setuptools installation script for pydatatypes package."""

from setuptools import setup, find_packages
from distutils.util import convert_path


# Get package version without importing it
version_ns = dict()
with open(convert_path('pydatatypes/version.py')) as fobj:
	exec(fobj.read(), version_ns)
version = version_ns['__version__']


setup(
	name='pydatatypes',
	version=version,
	description='Package for working with pseudo-statically-typed data structures',
	author='Jared Lumpe',
	author_email='mjlumpe@gmail.com',
	packages=find_packages(),
	install_requires=[
		'attrs>=17.3',
	],
)
