#!python
from distutils.core import setup

description = 'An alternative Django query language'

with open('README.txt') as file:
    long_description = file.read()

setup(name='Djaq',
      description=description,
      url='https://github.com/paul-wolf/djaq',
      author='Paul Wolf',
      author_email='paul.wolf@yewleaf.com',
      version='0.0.0',
      # version = module.__version__,
      packages=['djaq', ],
      license='MIT',
      long_description=long_description,
      classifiers=[
          'Development Status :: 2 - Pre-Alpha',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',

          'Programming Language :: Python',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Framework :: Django',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
      )
