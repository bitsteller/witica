from setuptools import setup, find_packages
import sys, os

version = '1.1'

setup(name='witica',
      version=version,
      description="Automates publishing content to the Web",
      long_description="""\
Witica is a new way to publish things on the internet. The goal is to make editing content on your website as easy as opening your favourite text editor, make a change and save the file.""",
      classifiers=["License :: OSI Approved :: MIT License",
                   "Development Status :: 3 - Alpha",
                   "Environment :: Console",
                   "Intended Audience :: Information Technology",
                   "Natural Language :: English",
                   "Operating System :: MacOS :: MacOS X",
                   "Operating System :: POSIX :: Linux",
                   "Programming Language :: JavaScript",
                   "Programming Language :: Python :: 2.7",
                   "Topic :: Internet :: WWW/HTTP",
                   "Topic :: Text Processing :: Markup :: HTML"], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='web dropbox html markdown javascript publishing incremental ftp',
      author='Nils Breyer',
      author_email='mail@witica.org',
      url='http://witica.org/',
      license='MIT License',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          "markdown>=2.6.7",
          "keyring>=10.0.2",
          "dropbox>=8.0.0",
          "kitchen>=1.2.4",
          "pillow>=3.4.2"
      ],
      entry_points= {
            "console_scripts": [
                  "witica = witica.main:main"
            ]},
      )