import io
import os
import sys
import json
import base64
import shutil
import hashlib
import tarfile
import datetime
import importlib
import subprocess
import urllib.error
import urllib.request

from contextlib import contextmanager

from cryptography.fernet import Fernet

# NOTE: This is a dummy to persuade Python's import mechanics into treating this as a package.
__path__ = os.path.dirname(__file__)


KEY = b"This is the secret key."
HOST = "localhost"
PORT = 7777


class NoSuchPackage(Exception):
    pass


PACKAGE_NAME = "pyk"
TOML_NAME = "pyk.toml"
JSON_NAME = "pyk.json"
BASEDIR = os.path.expanduser("~/.cache/pyk")


class Crypto:

    def __init__(self):
        hashed_key = hashlib.sha256(KEY).digest()
        self.fernet = Fernet(base64.b64encode(hashed_key))

    def encrypt(self, data):
        return self.fernet.encrypt(data)

    def decrypt(self, data):
        return self.fernet.decrypt(data)


class Logfile:

    def __init__(self, debug=False):
        self.buffer = io.StringIO()
        self.debug = debug

    def set_file(self, path):
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
        self.venv_dir = os.path.join(BASEDIR, "lib" if self.lib else "run", self.name)
        self.json_path = os.path.join(self.venv_dir, JSON_NAME)

        self.crypto = Crypto()

    def log(self, message):
        self.logfile.log(message)

    def prepare_download(self, command):
        self.log(f"get {self.url % command}")
        try:
            request = urllib.request.Request(self.url % command)
            with urllib.request.urlopen(request) as response:
                data = response.read()
                if command == "download":
                    data = self.crypto.decrypt(data)
                elif command == "info":
                    data = json.loads(data)

        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NoSuchPackage() from exc

        return data

    def get_remote_info(self):
        config = self.prepare_download("info")
        return config["version"], datetime.datetime.fromisoformat(config["date"]).timestamp()

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
        # FIXME detect python version changes.
        self.log(f"check if package {self.name!r} has changed")
        version, last_modified = self.get_remote_info()

        uptodate = True
        try:
            with open(self.json_path, encoding="utf-8") as fobj:
                install_date = json.load(fobj)["install_date"]
        except FileNotFoundError:
            uptodate = False
        else:
            try:
                uptodate = datetime.datetime.fromisoformat(install_date).timestamp() > last_modified
            except KeyError:
                uptodate = False

        if uptodate:
            self.log("package is up-to-date")
            self.load_config()
            return False

        self.log(f"package {self.name!r} was updated to version {version}")

        try:
            shutil.rmtree(self.venv_dir)
        except FileNotFoundError:
            pass

        os.makedirs(self.venv_dir)

        self.logfile.set_file(os.path.join(self.venv_dir, "pyk.log"))

        self.log(f"download package {self.name!r}")
        data = self.prepare_download("download")
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

        dt = datetime.datetime.fromisoformat(self.config["build_date"])
        self.log(f"build date: {dt:%Y-%m-%d %H:%M:%S}")
        self.log(f"version: {self.config['version']}")

    def save_config(self):
        self.config["install_date"] = datetime.datetime.now().isoformat()
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


class ImportHook:

    def find_spec(self, fullname, path, target=None):
        # pylint:disable=unused-argument
        if not fullname.startswith(PACKAGE_NAME + "."):
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
