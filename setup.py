"""Install the reel package."""
from setuptools import find_packages, setup

setup(
    license='MIT',
    name='reel',
    version_command='git describe --abbrev=0',
    author='Zach Thompson',
    author_email='zach@allotropic.com',
    url='http://github.com/zthompson47/reel',
    description='An async subprocess manager',
    long_description_content_type='text/x-rst',
    long_description=open('README.rst', 'r').read(),
    classifiers=[
        "Programming Language :: Python :: 3.5",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={'console_scripts': ['reel=reel.cli:enter']},
    install_requires=['trio>=0.10.0'],
    zip_safe=False,
    packages=find_packages(),
)
