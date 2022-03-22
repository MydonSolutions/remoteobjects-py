from distutils.core import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(name = 'remoteobjects',
    version = '1.0.0',
    description = 'Remote object access under a client-server model.',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    author = 'Ross Donnachie',
    author_email = 'code@radonn.co.za',
    url = 'https://github.com/MydonSolutions/remoteobjects-py',
    packages = ['remoteobjects.client', 'remoteobjects.server'],
    package_dir = {
        'remoteobjects.client': 'src/client',
        'remoteobjects.server': 'src/server',
    },
    classifiers = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',
        'Framework :: Flask',
    ],
    python_requires = ">= 3.6"
)