import config
import utils
import re
import shutil
import importlib
import importlib.util
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
            return version in utils.get_program_version(name) if version else True
        return False

    def _verify_python_dep(self, name, version):
        try:
            return version in utils.get_python_module_version(name) if version else True
        except ImportError:
            return False

    def _install_local_tool(self, dep, config):
        tool_config = config.get_tool_config(dep["name"])
        keys = tool_config.keys()
        if len(keys) > 1 or next(iter(keys)) not in ["path", "python", "script"]:
            raise Exception(f"Local tools may have up to one config parameter, either 'path', 'python' or 'script'. Found {list(keys)}.")

        key = next(iter(keys))
        if key == "path":
            pass
        elif key == "python":
            # no try/except - we want to fail if it doesn't work
            spec = importlib.util.spec_from_file_location(dep["name"], tool_config[key])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


            if hasattr(module, "setup"):
                module.setup(config.local_tools_dir())
            else:
                raise Exception(f"Module {tool_config[key]} does not implement `setup` function")

        else:  # key is "script"
            utils.run_process_print_output(tool_config[key])



    def _verify_dep(self, dep, default):

        to_check = dep["verifiable_name"] or dep["name"]
        how_to_check = dep["type"] or default

        if how_to_check == 'bin':
            return self._verify_binary_dep(to_check, dep["version"])
        else:
            return self._verify_python_dep(to_check, dep["version"])

    def _build_deps_and_run_install(self, params, deps, noun, config):
        if len(deps) == 0:
            return
        for dep in deps:
            if config.is_local_tool(dep["name"]):
                self._install_local_tool(dep, config)
                continue

            # we filter out git+.*, as these indicate python modules fetched
            # from git repositiories, without version information
            if dep["version"] and not dep["name"].startswith("git+"):
                params.append(f"{dep['name']}={dep['version']}")
            else:
                params.append(dep["name"])

        if len(params) == 0:
            # nothing to install
            return

        if utils.run_process_print_output(params):
            print(f"Succesfully installed {noun} dependencies")
        else:
            print(
                f"There was an error installing {noun} packages, see the log")

    def install(self, config):

        conda_params = ["conda", "install", "-y"]
        if config.conda_flags:
            conda_params.append(config.conda_flags())

        self._build_deps_and_run_install(conda_params, self._conda_deps,
                                         "conda", config)

        for dep in self._conda_deps:
            if not self._verify_dep(dep, "bin"):
                raise Exception(f"Conda dependency {dep['name']} was not installed properly")


        pip_params = ["pip", "install"]

        self._build_deps_and_run_install(pip_params, self._pip_deps, "pip", config)

        for dep in self._pip_deps:
            if not self._verify_dep(dep, "py"):
                raise Exception(f"PIP dependency {dep['name']} was not installed properly")


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

    req.install(cfg)
