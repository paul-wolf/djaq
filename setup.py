#!python
from distutils.core import setup
from setuptools import find_packages

description = "A string-based Django query language"

with open("README.txt") as file:
    long_description = file.read()

setup(
    name="Djaq",
    description=description,
    url="https://github.com/paul-wolf/djaq",
    author="Paul Wolf",
    author_email="paul.wolf@yewleaf.com",
    version="0.1.0",
    #  version = djaq.__version__,
    packages=find_packages(exclude=["*~"]),
    include_package_data=True,
    license="MIT",
    long_description=long_description,
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Framework :: Django",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
