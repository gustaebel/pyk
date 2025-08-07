# pyk

**pyk** is a minimal and highly experimental Python package runner and
importer. It fetches pre-built packages from a remote repository and runs or
imports them on demand — no installs, no setup. Just `pyk <package>` or `from
pyk.<package> import foo`.

The idea is admittedly a little insane — but it works for me.

## Features

- Custom repository server component with zero setup.
- Package building is straight-forward, no `setup.py` or `pyproject.toml`. Just
  say which files you want to put in the package.
- Only one third-party dependency: [cryptography](https://pypi.org/project/cryptography/)

## Usage

**IMPORTANT:** Change the `KEY` in `pyk.py` before use.

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
