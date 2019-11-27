import config
import re
import shutil
import sys
import os
import subprocess
import importlib
import conda.cli.python_api as Conda
from os.path import dirname, join, abspath, exists, isdir, isfile


class RequirementsManager:
    _conda_deps = []
    _pip_deps = []


    def _add_dep(self, list, dep):
        #parse entry: name[==version] [#(bin|py):name-to-check]
        m = self._regex.search(dep)
        if not m:
            raise Exception(f"Requirement {dep} not in a proper format")
        list.append((m.group(1), m.group(3), m.group(5), m.group(6)))


    def scan(self, target = None):
        if not target:
            workdir = self._requirements_dir
        else:
            workdir = join(self._requirements_dir, target)

        conda_file = join(workdir, "conda.txt")
        if isfile(conda_file):
            with open(conda_file, "r") as f:
                for dep in f:
                    dep = dep.strip()
                    if not dep or len(dep) == 0:
                        continue
                    self._add_dep(self._conda_deps, dep)

        pip_file = join(workdir, "pip.txt")
        if isfile(pip_file):
            with open(pip_file, "r") as f:
                for dep in f:
                    dep = dep.strip()
                    if not dep or len(dep) == 0:
                        continue
                    self._add_dep(self._pip_deps, dep)


    def _verify_binary_dep(self, name, version):
        if shutil.which(name):
            if version:
                return version in subprocess.run([name, '--version'], stdout=subprocess.PIPE).stdout.decode('utf-8')
            return True
        return False


    def _verify_python_dep(self, name, version):
        try:
            i = importlib.import_module(name)
            if version:
                return version in i.__version__
            return True
        except:
            return False


    def _verify_dep(self, dep, default):
        name, version, type, verify = dep

        to_check = verify or name
        how_to_check = type or default

        if how_to_check == 'bin':
            return self._verify_binary_dep(to_check, version)
        else:
            return self._verify_python_dep(to_check, version)

    def _build_deps_and_run_install(self, params, deps, noun):
        for dep in deps:
            if dep[1]: # version
                params.append(f"{dep[0]}={dep[1]}")
            else:
                params.append(dep[0])

        process = subprocess.Popen(params, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        while True:
            output = process.stdout.readline()
            if output == b'' and process.poll() is not None:
                break
            if output:
                print(output.decode(sys.stdout.encoding).strip("\n\r"))
        if process.poll() == 0:
            print(f"Succesfully installed {noun} dependencies")
        else:
            print(f"There was an error installing {noun} packages, see the log above")


    def install(self):
        installed_conda = []
        for dep in self._conda_deps:
            if self._verify_dep(dep, "bin"):
                installed_conda.append(dep)

        self._conda_deps = [x for x in self._conda_deps if x not in installed_conda]

        installed_pip = []
        for dep in self._pip_deps:
            if self._verify_dep(dep, "py"):
                installed_pip.append(dep)

        self._pip_deps = [x for x in self._pip_deps if x not in installed_pip]

        conda_params = ["conda", "install", "-y"]
        if "CONDA_FLAGS" in os.environ.keys():
            conda_params.append(os.environ["CONDA_FLAGS"])

        self._build_deps_and_run_install(conda_params, self._conda_deps, "conda")

        pip_params = ["pip", "install"]

        self._build_deps_and_run_install(pip_params, self._pip_deps, "pip")



    def __init__(self):
        self._requirements_dir = abspath(join(join(dirname(abspath(__file__)), ".."), "requirements"))
        if not isdir(self._requirements_dir):
            raise Exception("Missing requirements directory")
        #([^\ #]+) non-space, non # character -> package name
        #(==([^ #]+))? - two equality signs followed by version - optional
        # #(bin|py) - hash and information how to check the requirement
        # (\S+) - the requirement name to look for
        self._regex = re.compile(r"^([^\ #(==)]+)(==([^ #]+))?( ?#(bin|py):(\S+))?$")


def prepare():
    """
    Sets up the environment, verifying that all tools are present.
    If they are not, they are installed and/or configured.
    """
    #
    #Stages:
    #- verification of git submodules (not yet)
    #- lookup of dependencies depending on settings
    #- configuration of local tools
    #- conda installations

    #bin|py
    #conda -> default bin
    #pip - default py

    req = RequirementsManager()
    cfg = config.ConfigManager()

    # first scan for general dependencies
    req.scan()
    for target in cfg.get_all_parameters():
        req.scan(target)

    req.install()
