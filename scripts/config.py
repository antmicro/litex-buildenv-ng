import sys
import configparser
from os.path import dirname, join, abspath, exists, isfile


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
        return join(self._base_path, name + ".env")

    def cpu(self):
        return self._config[self.DEFAULT][self.CPU]

    def cpu_variant(self):
        return self._config[self.DEFAULT][self.CPU_VARIANT]

    def platform(self):
        return self._config[self.DEFAULT][self.PLATFORM]

    def target(self):
        return self._config[self.DEFAULT][self.TARGET]

    def firmware(self):
        return self._config[self.DEFAULT][self.FIRMWARE]

    def cpu_arch(self):
        return {
            "lm32": "lm32",
            "mor1kx": "or1k",
            "vexriscv": "riscv32",
            "picorv32": "riscv32",
            "minerva": "riscv32",
        }.get(self.cpu())

    def get_all_parameters(self):
        return (self.cpu(), self.cpu_arch(), self.cpu_variant(),
                self.platform(), self.target(), self.firmware())

    def get_local_tools(self):
        return [
            x for x in self._config.sections() + self._tools.sections()
            if x != self.DEFAULT
        ]

    def get_tool_config(self, tool):
        if self._config.has_section(tool):
            return self._config[tool]
        if self._tools.has_section(tool):
            return self._tools[tool]

    def print_config(self):
        print(f'''Current configuration settings:
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

        self._base_path = abspath(join(dirname(abspath(__file__)), ".."))
        self._config_file = self.__get_config_file(name)
        self._tools_file = self.__get_config_file("local-tools")

        for file in [self._config_file, self._tools_file]:
            if not exists(file):
                with open(file, "a"):
                    pass
            elif not isfile(file):
                print(f'Could not open "{file}" file')
                sys.exit(-1)

        self._config = configparser.ConfigParser()
        self._config.read_file(open(self._config_file))
        self._tools = configparser.ConfigParser()
        self._tools.read_file(open(self._tools_file))

        if not self._config.has_section(self.DEFAULT):
            self._config.add_section(self.DEFAULT)

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
                self.CPU, self.CPU_VARIANT, self.PLATFORM, self.TARGET,
                self.FIRMWARE
        ]:
            if not self._config.has_option(self.DEFAULT, setting):
                print(
                    f'Missing section "{setting}". Please fill the '
                    f'{self._config_file} or provide a "--{setting}" parameter'
                )
                sys.exit(-1)

        with open(self._config_file, "w") as file:
            self._config.write(file)

        self.print_config()