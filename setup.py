import os
import re

from setuptools import find_packages, setup

HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as handle:
        return handle.read()


def find_version():
    match = re.search(r'__version__ = "([^"]+)"', read("phototidy", "__init__.py"))
    if not match:
        raise RuntimeError("version string not found")
    return match.group(1)


setup(
    name="photo-tidy",
    version=find_version(),
    description="File photos into year/month folders using their EXIF capture dates",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    license="MIT",
    packages=find_packages(exclude=("tests",)),
    python_requires=">=3.8",
    entry_points={"console_scripts": ["photo-tidy = phototidy.cli:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Utilities",
    ],
)
