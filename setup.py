from setuptools import setup
from os import path

__file_dir__, _ = path.split(__file__)
with open(path.join(__file_dir__, "README.md"), "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(name='remoteobjects',
      version='1.7.1',
      description='Remote object access under a client-server model.',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='Ross Donnachie',
      author_email='code@radonn.co.za',
      url='https://github.com/MydonSolutions/remoteobjects-py',
      packages=['remoteobjects.client', 'remoteobjects.server'],
      package_dir={
          'remoteobjects.client': path.join(__file_dir__, 'src/client'),
          'remoteobjects.server': path.join(__file_dir__, 'src/server'),
      },
      classifiers=[
          'Programming Language :: Python :: 3',
          'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
          'Operating System :: OS Independent',
          'Development Status :: 4 - Beta',
          'Framework :: Flask',
      ],
      python_requires=">= 3.6"
      )
