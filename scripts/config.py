import sys
import os
import platform
import configparser
import os.path as Path
from log import Log


class Singleton:
    _state = {}

    def __init__(self):
        self.__dict__ = self._state


class ConfigManager(Singleton):

    DEFAULT = "config"
    CPU = "cpu"
    CPU_VARIANT = "cpu-variant"
    PLATFORM = "platform"
    TARGET = "target"
    FIRMWARE = "firmware"

    def __get_config_file(self, name):
        return Path.join(self._base_path, name + ".env")

    def is_local_tool(self, name):
        return name in self.get_local_tools()

    def cpu(self):
        return self._config[self.DEFAULT][self.CPU]

    def cpu_variant(self):
        if self.CPU_VARIANT in self._config[self.DEFAULT].keys():
            return self._config[self.DEFAULT][self.CPU_VARIANT]
        else:
            return None

    def platform(self):
        return self._config[self.DEFAULT][self.PLATFORM]

    def target(self):
        return self._config[self.DEFAULT][self.TARGET]

    def firmware(self):
        return self._config[self.DEFAULT][self.FIRMWARE]

    def conda_flags(self):
        return self._conda_flags

    def local_tools_dir(self):
        return self._local_tools

    def cpu_arch(self):
        return {
            "lm32": "lm32",
            "mor1kx": "or1k",
            "vexriscv": "riscv32",
            "picorv32": "riscv32",
            "minerva": "riscv32",
        }.get(self.cpu())

    def get_all_parameters(self):
        self.toolchain = f'{self.cpu()}.{self.firmware()}'
        return (self.cpu(), self.cpu_arch(), self.cpu_variant(),
                self.platform(), self.target(), self.firmware(),
                self.toolchain)

    def get_local_tools(self):
        return [
            x for x in self._config.sections() + self._tools.sections()
            if x != self.DEFAULT
        ]

    def get_shell(self):
        host = platform.system()
        if host in ["Darwin", "Linux"]:
            return "/bin/bash"
        else:
            return "cmd"

    def get_tool_config(self, tool):
        if self._config.has_section(tool):
            return self._config[tool]
        if self._tools.has_section(tool):
            return self._tools[tool]

    def print_config(self):
        Log.log(f'''Current configuration settings:
             CPU:  {self.cpu()}
CPU architecture:  {self.cpu_arch()}
     CPU variant:  {self.cpu_variant()}
        Platform:  {self.platform()}
          Target:  {self.target()}
        Firmware:  {self.firmware()}
        ''')

    def __init__(self):
        Singleton.__init__(self)

    def init(self, name, cpu, cpu_variant, platform, target, firmware):

        if "CONDA_FLAGS" in os.environ.keys():
            self._conda_flags = os.environ["CONDA_FLAGS"]
        else:
            self.conda_flags = None

        if "BUILDENV_LOCAL_TOOLS" in os.environ.keys():
            self._local_tools = os.environ["BUILDENV_LOCAL_TOOLS"]
        else:
            self._local_tools = None

        if "BUILD_DIR" in os.environ.keys():
            self._build_dir = os.environ["BUILD_DIR"]
        else:
            self._build_dir = None

        self._base_path = Path.abspath(
            Path.join(Path.dirname(Path.abspath(__file__)), ".."))
        self._config_file = self.__get_config_file(name)
        self._tools_file = self.__get_config_file("local-tools")

        for file in [self._config_file, self._tools_file]:
            if not Path.exists(file):
                with open(file, "a"):
                    pass
            elif not Path.isfile(file):
                Log.log(f'Could not open "{file}" file')
                sys.exit(-1)

        self._config = configparser.ConfigParser()
        self._config.read_file(open(self._config_file))
        self._tools = configparser.ConfigParser()
        self._tools.read_file(open(self._tools_file))

        if not self._config.has_section(self.DEFAULT):
            self._config.add_section(self.DEFAULT)

        self._default_section = self.DEFAULT

        if cpu:
            self._config[self.DEFAULT][self.CPU] = cpu

        if cpu_variant:
            self._config[self.DEFAULT][self.CPU_VARIANT] = cpu_variant

        if platform:
            self._config[self.DEFAULT][self.PLATFORM] = platform

        if target:
            self._config[self.DEFAULT][self.TARGET] = target

        if firmware:
            self._config[self.DEFAULT][self.FIRMWARE] = firmware

        for setting in [
                self.CPU, self.PLATFORM, self.TARGET,
                self.FIRMWARE
        ]:
            if not self._config.has_option(self.DEFAULT, setting):
                Log.log(
                    f'Missing section "{setting}". Please fill the '
                    f'{self._config_file} or provide a "--{setting}" parameter'
                )
                sys.exit(-1)

        with open(self._config_file, "w") as file:
            self._config.write(file)

        self.print_config()
