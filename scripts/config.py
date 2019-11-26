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
        return join(self.base_path, name + ".env")

    def cpu(self):
        return self.config[self.DEFAULT][self.CPU]

    def cpu_variant(self):
        return self.config[self.DEFAULT][self.CPU_VARIANT]

    def platform(self):
        return self.config[self.DEFAULT][self.PLATFORM]

    def target(self):
        return self.config[self.DEFAULT][self.TARGET]

    def firmware(self):
        return self.config[self.DEFAULT][self.FIRMWARE]

    def get_local_tools(self):
        return [x for x in self.config.sections() + self.tools.sections() if x != self.DEFAULT]

    def get_tool_config(self, tool):
        if self.config.has_section(tool):
            return self.config[tool]
        if self.tools.has_section(tool):
            return self.tools[tool]

    def print_config(self):
        print(f'''Current configuration settings:
        CPU:  {self.cpu()}
CPU variant:  {self.cpu_variant()}
   Platform:  {self.platform()}
     Target:  {self.target()}
   Firmware:  {self.firmware()}
        ''')

    def __init__(self):
        Singleton.__init__(self)

    def init(self, name, cpu, cpu_variant, platform, target, firmware):

        self.base_path = abspath(join(dirname(abspath(__file__)), ".."))
        self.file = self.__get_config_file(name)

        if not exists(self.file):
            with open(self.file, "a"):
                pass
        elif not isfile(self.file):
            print(f'Could not open "{self.file} file')
            sys.exit(-1)

        self.config = configparser.ConfigParser()
        self.config.read_file(open(self.file))
        self.tools = configparser.ConfigParser()
        self.tools.read_file(open(self.__get_config_file("local-tools")))

        if not self.config.has_section(self.DEFAULT):
            self.config.add_section(self.DEFAULT)

        if cpu is not None:
            self.config[self.DEFAULT][self.CPU] = cpu

        if cpu_variant is not None:
            self.config[self.DEFAULT][self.CPU_VARIANT] = cpu_variant

        if platform is not None:
            self.config[self.DEFAULT][self.PLATFORM] = platform

        if target is not None:
            self.config[self.DEFAULT][self.TARGET] = target

        if firmware is not None:
            self.config[self.DEFAULT][self.FIRMWARE] = firmware

        for setting in [self.CPU, self.CPU_VARIANT, self.PLATFORM, self.TARGET, self.FIRMWARE]:
            if not self.config.has_option(self.DEFAULT, setting):
                print(f'Missing section "{setting}". Please fill the {self.file} or provide a "--{setting}" parameter')
                sys.exit(-1)

        with open(self.file, "w") as file:
            self.config.write(file)

        self.print_config()
