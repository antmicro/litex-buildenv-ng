import config
import re
import shutil
import sys
import os
import subprocess
import importlib
import os.path as Path


class RequirementsManager:
    def _add_dep(self, list, dep):
        # parse entry: name[==version] [#(bin|py):name-to-check]
        m = self._regex.search(dep)
        if not m:
            raise Exception(f"Requirement {dep} not in a proper format")
        dependency = {}
        dependency["name"] = m.group(1)
        dependency["version"] = m.group(3)
        dependency["type"] = m.group(5)
        dependency["verifiable_name"] = m.group(6)
        list.append(dependency)

    def scan(self, target=None):
        if not target:
            workdir = self._requirements_dir
        else:
            workdir = Path.join(self._requirements_dir, target)

        conda_file = Path.join(workdir, "conda.txt")
        if Path.isfile(conda_file):
            with open(conda_file, "r") as f:
                for dep in f:
                    dep = dep.strip()
                    if not dep or len(dep) == 0:
                        continue
                    self._add_dep(self._conda_deps, dep)

        pip_file = Path.join(workdir, "pip.txt")
        if Path.isfile(pip_file):
            with open(pip_file, "r") as f:
                for dep in f:
                    dep = dep.strip()
                    if not dep or len(dep) == 0:
                        continue
                    self._add_dep(self._pip_deps, dep)

    def _verify_binary_dep(self, name, version):
        if shutil.which(name):
            if version:
                return version in subprocess.run(
                    [name, '--version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT).stdout.decode('utf-8')
            return True
        return False

    def _verify_python_dep(self, name, version):
        try:
            i = importlib.import_module(name)
            if version:
                return version in i.__version__
            return True
        except ImportError:
            return False

    def _verify_dep(self, dep, default):

        to_check = dep["verifiable_name"] or dep["name"]
        how_to_check = dep["type"] or default

        if how_to_check == 'bin':
            return self._verify_binary_dep(to_check, dep["version"])
        else:
            return self._verify_python_dep(to_check, dep["version"])

    def _build_deps_and_run_install(self, params, deps, noun):
        if len(deps) == 0:
            return
        for dep in deps:
            # we filter out git+.*, as these indicate python modules fetched
            # from git repositiories, without version information
            if dep["version"] and not dep["name"].startswith("git+"):
                params.append(f"{dep['name']}={dep['version']}")
            else:
                params.append(dep["name"])

        process = subprocess.Popen(params,
                                   stderr=subprocess.STDOUT,
                                   stdout=subprocess.PIPE)
        while True:
            output = process.stdout.readline()
            if output == b'' and process.poll() is not None:
                break
            if output:
                print(output.decode(sys.stdout.encoding).strip("\n\r"))
        if process.poll() == 0:
            print(f"Succesfully installed {noun} dependencies")
        else:
            print(
                f"There was an error installing {noun} packages, see the log")

    def install(self):
        installed_conda = []
        for dep in self._conda_deps:
            if self._verify_dep(dep, "bin"):
                installed_conda.append(dep)

        self._conda_deps = [
            x for x in self._conda_deps if x not in installed_conda
        ]

        installed_pip = []
        for dep in self._pip_deps:
            if self._verify_dep(dep, "py"):
                installed_pip.append(dep)

        self._pip_deps = [x for x in self._pip_deps if x not in installed_pip]

        conda_params = ["conda", "install", "-y"]
        if "CONDA_FLAGS" in os.environ.keys():
            conda_params.append(os.environ["CONDA_FLAGS"])

        self._build_deps_and_run_install(conda_params, self._conda_deps,
                                         "conda")

        pip_params = ["pip", "install"]

        self._build_deps_and_run_install(pip_params, self._pip_deps, "pip")

    def __init__(self):
        self._conda_deps = []
        self._pip_deps = []
        self._requirements_dir = Path.abspath(
            Path.join(Path.join(Path.dirname(Path.abspath(__file__)), ".."),
                      "requirements"))
        if not Path.isdir(self._requirements_dir):
            raise Exception("Missing requirements directory")
        # ([^\ #]+) non-space, non # character -> package name
        # (==([^ #]+))? - two equality signs followed by version - optional
        # #(bin|py) - hash and information how to check the requirement
        # (\S+) - the requirement name to look for
        self._regex = re.compile(
            r"^([^\ #(==)]+)(==([^ #]+))?( ?#(bin|py):(\S+))?$")


def prepare():
    """
    Sets up the environment, verifying that all tools are present.
    If they are not, they are installed and/or configured.
    """
    #
    # Stages:
    # - verification of git submodules (not yet)
    # - lookup of dependencies depending on settings
    # - configuration of local tools
    # - conda installations

    # bin|py
    # conda -> default bin
    # pip - default py

    req = RequirementsManager()
    cfg = config.ConfigManager()

    # first scan for general dependencies
    req.scan()
    for target in cfg.get_all_parameters():
        req.scan(target)

    req.install()
