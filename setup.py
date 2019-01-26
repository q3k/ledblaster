from setuptools import setup, find_packages

import versioneer

setup(
    name='ledblaster',
    version=versioneer.get_version(),
    author='ledblaster Authors',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Video :: Display",
    ],
    install_requires=[
        'migen',
    ],
    dependency_links=[
        "git+https://github.com/m-labs/migen.git#egg=migen",
    ],
    entry_points={
        "console_scripts": [
            "lbgw = gateware.cli:main"
       ],
    },
)
