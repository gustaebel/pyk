# pyk

**pyk** is a minimal and highly experimental Python package runner and
importer. It fetches pre-built packages from a remote repository and runs or
imports them on demand — no installs, no setup. Just `pyk pkgname` or `from
pyk.pkgname import foo`.

## Features

- Easy deployment of custom Python scripts and libraries with a single command.
- Simple repository server with zero setup.
- Package building is straight-forward, no `setup.py` or `pyproject.toml`. Just
  say which files you want to put in the package. 
- Only one third-party dependency needed on the client side:
  [cryptography](https://pypi.org/project/cryptography/)

## Usage

**IMPORTANT:** Change the `KEY` in `pyk.py` before deploying.

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
