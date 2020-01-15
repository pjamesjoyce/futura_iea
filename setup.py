"""
To create the wheel run - python setup.py bdist_wheel
"""

from setuptools import setup
import os, sys

PACKAGE_NAME = 'futura_iea'
VERSION = '0.0.1'

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    #packages=packages,
    author="P. James Joyce",
    author_email="pjamesjoyce@gmail.com",
    license="BSD 3-Clause License",
    #package_data={'futura': my_package_files},
    entry_points={
        'futura_plugins': [
            'iea = futura_iea.iea:main'
        ],
        'console_scripts': [
            'iea = futura_iea.iea:main'
        ]
    },
    # install_requires=[
    # ],
    #include_package_data=True,
    url="https://github.com/pjamesjoyce/{}/".format(PACKAGE_NAME),
    download_url="https://github.com/pjamesjoyce/{}/archive/{}.tar.gz".format(PACKAGE_NAME, VERSION),
    long_description="a plugin", # open('README.md').read(),
    description='A plugin for a tool for LCA',
    keywords=['LCA', 'Life Cycle Assessment', 'Foreground system', 'Background system', 'Foreground model',
              'Fully parameterised'],
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Mathematics',
        'Topic :: Scientific/Engineering :: Visualization',
    ],
)