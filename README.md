# pyk

**pyk** is a minimal and experimental system to distribute packages to clients
in a home network. Scripts (Python, shell, etc.) or Python libraries are
packaged and then uploaded to a server. On the client side, a simple `pyk
<pkgname>` downloads and runs a packaged script. In Python, `from pyk import
<pkgname>` downloads and imports a packaged library. Minimal setup is needed. 


## How it works

I regularly write scripts (Python and Bash) and Python libraries that I want to
use on various computers and VMs in my home network.

I was looking for an easier way to deploy these projects instead of copying
them to other hosts by hand or packaging and installing them using the distro's
package manager. Both these approaches are quite laborious, especially during
the initial development and testing phase that makes frequent updates
necessary.

**pyk** makes all this as easy as possible. It provides of a small repository
server and a runner that will be installed on each client. The runner is
responsible for downloading, installing and running packages from the
repository. Before every run, it checks for a new package version and updates
the local installation if necessary.

This way, deploying and updating a package is as easy as uploading it to the
repository. All the clients will use the new version the next time the package
is run.


## Features

- Fast and easy auto-updating deployment of small software projects, e.g.
  custom scripts (Python, shell, etc.) and Python libraries.
- Simplifies simultaneous development on multiple different machines.
- Independent from distribution package management.
- Straight-forward building of packages, no `setup.py` or `pyproject.toml`.
- Restricted and secure access to the package repository using basic symmetric
  [Fernet](https://cryptography.io/en/latest/fernet/) encryption.
- Only one single third-party dependency needed on the client side:
  [cryptography](https://pypi.org/project/cryptography/)


## Installation

Edit `config.toml`. Then do this as root:

```sh
$ python setup.py install
$ install -Dt /etc/pyk config.toml
```

Start the server on the host as specified in `config.toml`:

```sh
$ pyk --server -v pyk.db
```


## Usage

### Example script `foo.py`

This is the file we want to distribute. It can be used both as a script or be
imported as a module. For it to be called as a script it must contain a shebang
line (`#!`) and be set executable.

```py
#!/usr/bin/env python3

import sys

def bar(x):
    print(x ** 2)

if __name__ == "__main__":
    bar(int(sys.argv[1]))
```

### Creating and using a runner package

1. Create a `pyk.toml` file:
   ```toml
   name = "foo"
   run = "foo.py"
   ```
2. Build and upload the runner package to the repository:
   ```sh
   $ pyk --build
   ```
3. You can now run `foo.py` on every client that can connect to the repository:
   ```sh
   $ pyk foo 8
   64
   ```

### Creating and using a library package

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
3. You can now import `foo.py` on every client that can connect to the
   repository using the *pyk* pseudo package.
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
