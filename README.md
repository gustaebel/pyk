# pyk

**pyk** is a minimal and highly experimental Python package runner and
importer. It fetches pre-built packages from a remote repository and runs or
imports them on demand - no installs, no setup. Just `pyk pkgname` or `from
pyk.pkgname import foo`.

## What it does

I regularly write small helper scripts (Python and Bash) that I want to use on
the various computers and VMs running Arch Linux and Debian in my home network.
Distributing these is tedious. If you want to do it right, the best solution
for this is to create distribution packages for these scripts. In many cases,
however, it is necessary to create packages for both distributions I use, and
then I have to log in to all the hosts where I want to use them and install
them there. This has to be repeated for every update while ironing out the
bugs.

**pyk** tries to make all this as easy as possible. It consists of a small
repository server and a loader which is the one thing that has to be installed
on the hosts exactly once. Creating a package is easy, the most basic config
for this is just two lines of TOML. This package is uploaded to the repository
with a simple command. On the hosts, the loader is used to execute these
packages. Before doing this, the loader checks if there is a new version
available in the repository, and if yes, downloads it and sets it up before
continuing.

## Features

- Fast and easy pull-based deployment of small software projects, e.g. custom
  scripts (Python, shell, etc.) and Python libraries.
- Simplifies development when the machine where the project is developed is
  different from the machine where it is tested / used.
- Fast turnaround times while developing and debugging scripts.
- Independent from distribution package management.
- Simple repository server with near-zero setup.
- Restricted and secure access to the package repository using basic symmetric
  [Fernet](https://cryptography.io/en/latest/fernet/) encryption.
- Python package building is straight-forward, no `setup.py` or
  `pyproject.toml`. Just say which files you want to put in the package. 
- Only one single third-party dependency needed on the client side:
  [cryptography](https://pypi.org/project/cryptography/)

## Usage

Before getting started, you must create the same configuration file
`etc/pyk/config.toml` on every host:

```toml
KEY = "Secret keyphrase"        # change this!
HOST = "host.domain.tld"
PORT = 7777
```

### Example script `foo.py`

```py
#!/usr/bin/env python3

import sys

def bar(x):
    print(x ** 2)

if __name__ == "__main__":
    bar(int(sys.argv[1]))
```

### Create and use a runner package

1. Create a `pyk.toml` file:
   ```toml
   name = "foo"
   run = "foo.py"
   ```
2. Build and upload the runner package to the repository:
   ```sh
   $ pyk --build
   ```
3. You can now run `foo.py` on every host that can connect to the repository:
   ```sh
   $ pyk foo 8
   64
   ```

### Create and use a library package

1. Create a `pyk.toml` file:
   ```toml
   name = "foo"
   lib = "foo.py"       # `lib` instead of `run`
   ```
2. Upload the library package to the repository. Libraries and runners are
   stored separately in the repository, so they may both have the same name.
   ```sh
   $ pyk --build
   ```
3. You can now run `foo.py` on every host that can connect to the repository:
   ```sh
   $ python
   Python 3.13.5 (main, Jun 21 2025, 09:35:00) [GCC 15.1.1 20250425] on linux
   Type "help", "copyright", "credits" or "license" for more information.
   >>> from pyk.foo import bar
   >>> bar(8)
   64
   ```

## pyk.toml

An example config for a module/package:

```toml
# The name of the package.
name = "foo"

# Variant 1: The module/package that will be imported when `from pyk import
# foo` is called.
lib = "bar.py" | "bar"

# Variant 2: The script name that will be executed when `pyk foo ...` is called
# in the shell.
run = "bar.py"

# [optional] A list of modules/packages from the source directory that will be
# included in the package.
libraries = ["foo.py", "baz"]

# [optional] A list of dependencies which will be installed in the virtual
# environment.
dependencies = ["rich", "requests"]

# [optional] A list of accessory directories and files that will be included in
# the package.
extras = ["README.md"]
```
