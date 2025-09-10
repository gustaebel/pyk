#
# pyk - A minimal and highly experimental Python packaging system for easy
#       deployment. Run and import packages directly from a remote server.
#
# Copyright (c) 2025, Lars Gustäbel
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import io
import os
import sys
import json
import base64
import shutil
import urllib.error
import urllib.request
import asyncio
import hashlib
import tarfile
import tomllib
import platform
import importlib
import importlib.util
import subprocess

from datetime import datetime
from contextlib import contextmanager

from cryptography.fernet import Fernet


CONFIG_PATH = "/etc/pyk/config.toml"

try:
    with open(CONFIG_PATH, "rb") as fobj:
        config = tomllib.load(fobj)
except FileNotFoundError:
    print(f"ERROR: missing config {CONFIG_PATH!r}", file=sys.stderr)
    sys.exit(123)
else:
    try:
        KEY = config["KEY"].encode("utf-8")
        HOST = config["HOST"]
        PORT = config["PORT"]
    except KeyError as exc:
        print(f"ERROR: missing key {exc} in config {CONFIG_PATH!r}", file=sys.stderr)
        sys.exit(123)


class NoSuchPackage(Exception):
    pass


PACKAGE_NAME = "pyk"
TOML_NAME = "pyk.toml"
JSON_NAME = "pyk.json"
CACHE_DIR = os.path.expanduser("~/.cache/pyk")
NODE = platform.node()


class Crypto:

    def __init__(self):
        hashed_key = hashlib.sha256(KEY).digest()
        self.fernet = Fernet(base64.b64encode(hashed_key))

    def encrypt(self, data):
        return self.fernet.encrypt(data)

    def decrypt(self, data):
        return self.fernet.decrypt(data)


class Logfile:
    """Log file class that buffers messages until a file is connected.
    """

    def __init__(self, debug=False):
        self.buffer = io.StringIO()
        self.debug = debug

    def connect_file(self, path):
        # pylint:disable=consider-using-with
        self.fobj = open(path, "w", encoding="utf-8")
        self.fobj.write(self.buffer.getvalue())
        self.buffer = None

    def log(self, message):
        if self.buffer is not None:
            fobj = self.buffer
        else:
            fobj = self.fobj

        print(message, file=fobj, flush=True)

        if self.debug:
            print(f"PYK: {message}", file=sys.stderr, flush=True)


class Package:

    # XXX make this python version aware?

    def __init__(self, name, lib=False, debug=False):
        self.name = name
        self.lib = lib
        self.logfile = Logfile(debug)

        self.url = f"http://{HOST}:{PORT}/%s/{'lib' if self.lib else 'run'}/{self.name}"
        self.venv_dir = os.path.join(CACHE_DIR, "lib" if self.lib else "run", self.name)
        self.json_path = os.path.join(self.venv_dir, JSON_NAME)

        self.crypto = Crypto()

    def log(self, message):
        self.logfile.log(message)

    def server_command(self, command):
        self.log(f"get {self.url % command}")
        try:
            request = urllib.request.Request(self.url % command, headers={"Pyk-Node": NODE})
            with urllib.request.urlopen(request) as response:
                return json.load(response)

        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NoSuchPackage() from exc

    def get_remote_version(self):
        return self.server_command("info")["version"]

    @classmethod
    @contextmanager
    def open_archive(cls, data):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            yield tar

    @classmethod
    def extract_config(cls, data):
        with cls.open_archive(data) as tar:
            for t in tar:
                if t.name == JSON_NAME:
                    fobj = tar.extractfile(t)
                    return json.load(fobj)
            else:
                raise ValueError("not a valid package file")

    def sync(self):
        """Check if the remote package was updated. If yes, remove the outdated package from the
           cache and download the current version. If the server is unreachable, use the cached
           package if there is one but warn.
        """
        # FIXME detect python version changes.
        self.log(f"check if package {self.name!r} has changed")
        try:
            remote_version = self.get_remote_version()
        except urllib.error.URLError as exc:
            if os.path.exists(self.json_path):
                print(f"WARNING: unable to reach {HOST}:{PORT}", file=sys.stderr)
                print("WARNING: falling back on cached package", file=sys.stderr)
                self.load_config()
                return False
            else:
                print(f"ERROR: unable to reach {HOST}:{PORT}", file=sys.stderr)
                sys.exit(123)
        else:
            uptodate = True
            try:
                with open(self.json_path, encoding="utf-8") as fobj:
                    local_version = json.load(fobj)["version"]
            except FileNotFoundError:
                uptodate = False
            else:
                self.log(f"local version: {local_version} / remote version: {remote_version}")
                uptodate = local_version == remote_version

        if uptodate:
            self.log("package is up-to-date")
            self.load_config()
            return False

        try:
            shutil.rmtree(self.venv_dir)
        except FileNotFoundError:
            pass

        os.makedirs(self.venv_dir)

        self.logfile.connect_file(os.path.join(self.venv_dir, "pyk.log"))

        self.log(f"download package {self.name!r}")
        data = self.server_command("download")
        data = self.crypto.decrypt(data["data"])

        self.log(f"extract package {self.name!r} to {self.venv_dir!r}")
        with self.open_archive(data) as tar:
            tar.extractall(self.venv_dir)

        self.load_config()
        self.prepare_dependencies()
        self.save_config()
        return True

    def load_config(self):
        with open(self.json_path, encoding="utf-8") as fobj:
            self.config = json.load(fobj)

        dt = datetime.fromisoformat(self.config["build_date"])
        self.log(f"build date: {dt:%Y-%m-%d %H:%M:%S}")
        self.log(f"version: {self.config['version']}")

    def save_config(self):
        self.config["install_date"] = datetime.now().isoformat()
        with open(self.json_path, "w", encoding="utf-8") as fobj:
            json.dump(self.config, fobj, indent=4)

    def prepare_dependencies(self):
        for dependency in self.config.get("dependencies", []):
            args = ["pip", "install", "--no-warn-conflicts", "--target", self.venv_dir, dependency]
            self.log(" ".join(args))
            try:
                subprocess.check_call(args, stdout=self.logfile.fobj, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print(f"ERROR: pip install had errors installing {dependency!r}", file=sys.stderr)
                print(f"ERROR: see {self.logfile.fobj.name!r} for details", file=sys.stderr)
                sys.exit(123)

    def run(self, argv):
        run = self.config.get("run")
        if run is None:
            raise ValueError(f"missing 'run' variable in {JSON_NAME}")

        run = os.path.join(self.venv_dir, run)

        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "").split(os.pathsep)
        pythonpath.insert(0, self.venv_dir)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
        os.execve(run, [run] + argv, env)

    async def wait_for_update(self):
        version = await asyncio.to_thread(self.get_remote_version)
        while True:
            try:
                response = await asyncio.to_thread(urllib.request.urlopen, self.url % "watch")
                data = await asyncio.to_thread(json.load, response)
                if version != data["version"]:
                    return data

            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise NoSuchPackage() from exc
                await asyncio.sleep(5)


class ImportHook:

    def find_spec(self, fullname, path, target=None):
        # pylint:disable=unused-argument
        if fullname == f"{PACKAGE_NAME}.__main__":
            return None
        elif not fullname.startswith(PACKAGE_NAME + "."):
            return None

        name = fullname.split(".", 1)[1]

        package = Package(name, lib=True)
        try:
            package.sync()
        except NoSuchPackage:
            # pylint:disable=raise-missing-from
            raise ModuleNotFoundError(f"No pyk module named {name!r}")

        path = os.path.join(package.venv_dir, package.config["lib"])
        if os.path.isdir(path):
            path = os.path.join(path, "__init__.py")

        loader = importlib.machinery.SourceFileLoader(fullname, path)
        return importlib.util.spec_from_loader(fullname, loader=loader)


sys.meta_path.append(ImportHook())


def pyk(name, module_name=None):
    if module_name is None:
        module_name = name
    package = Package(name, lib=True)
    package.sync()
    sys.path.insert(0, package.venv_dir)
    return importlib.import_module(module_name)
