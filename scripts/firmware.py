import config
import sys
import os
import os.path as Path
import git
import re
import subprocess
# from log import Log


class Progress(git.remote.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print('update(%s, %s, %s)' % (cur_count, max_count, message))


class FirmwareManager:

    FIRMWARE_OPT = ['test', 'load', 'flash', 'connect', 'clear']
    FIRMWARE_TARGET = ['linux', 'zephyr', 'micropython', 'hdmi2usb']

    # Linux defaults:
    LINUX = {
        'linux-mor1kx': 'https://github.com/timvideos/linux-litex.git',
        'linux-vexriscv': 'https://github.com/timvideos/linux-litex.git',
        'linux-vexriscv-buildroot': 'https://github.com/torvalds/linux.git'
    }
    LINUX_BRANCH = {
        'linux-mor1kx': 'master-litex',
        'linux-vexriscv': 'master-litex',
        'linux-vexriscv-buildroot': 'v5.0'
    }
    LINUX_DEFCONFIG = {
        'linux-vexriscv': 'https://antmicro.com/projects/renode/litex-buildenv/litex_vexriscv_linux.config'
    }
    ROOTFS = {
        'linux-mor1kx': "https://ozlabs.org/~joel/openrisc-rootfs.cpio.gz",
        'linux-vexriscv': "https://antmicro.com/projects/renode/litex-buildenv/riscv32-rootfs.cpio",
        'linux-vexriscv-buildroot': "https://antmicro.com/projects/renode/litex-buildenv/riscv32-rootfs.cpio"
    }
    DTB = {
        'linux-vexriscv': "https://antmicro.com/projects/renode/litex-buildenv/rv32.dtb"
    }
    BUILDROOT = {
        'linux-vexriscv-buildroot': "https://github.com/buildroot/buildroot.git"
    }
    LLV = {
        'linux-vexriscv-buildroot': "https://github.com/litex-hub/linux-on-litex-vexriscv.git"
    }

    LINUX_DEFAULT = {
        'firmware-url': LINUX,
        'firmware-branch': LINUX_BRANCH,
        'linux-config-url': LINUX_DEFCONFIG,
        'rootfs-url': ROOTFS,
        'dtb-url': DTB,
        'buildroot-url': BUILDROOT,
        'llv-url': LLV
    }

    # Zephyr defaults:
    ZEPHYR_DEFAULT = {
        'firmware-url': None,
        'firmware-branch': None,
    }

    # FuPy defaults:
    FUPY_DEFAULT = {
        'firmware-url': None,
        'firmware-branch': None,
    }

    # Build low-level firmware + LiteX defaults:
    BUILD_FIRMWARE_DEFAULT = {
        'tftp-iprange': '192.168.100',
    }

    # This builds low-level firmware and sets up LiteX stuff in build dir
    def build_firmware(self):
        for opt in self.BUILD_FIRMWARE_DEFAULT.keys():
            if opt not in self.cfg._config[self.cfg._default_section].keys():
                self.ADDITIONAL_OPT[opt] = self.BUILD_FIRMWARE_DEFAULT[opt]
            else:
                self.ADDITIONAL_OPT[opt] = self.cfg._config[self.cfg._default_section][opt]

        arg_list = ['python', 'scripts/make.py',
            '--platform',
            self.cfg.platform(),
            '--target',
            self.cfg.target(),
            '--cpu-type',
            self.cfg.cpu(),
            '--iprange',
            self.ADDITIONAL_OPT["tftp-iprange"],
            '--cpu-variant',
            self.cfg.cpu_variant(),
            '--no-compile-gateware',
        ]

        if len(self.ADDITIONAL_OPT["platform-option"]) > 1:
            arg_list.append('-Op')
            for arg in self.ADDITIONAL_OPT["platform-option"]:
                arg_list.append(arg)
        if len(self.ADDITIONAL_OPT["target-option"]) > 1:
            arg_list.append('-Ot')
            for arg in self.ADDITIONAL_OPT["target-option"]:
                arg_list.append(arg)
        if len(self.ADDITIONAL_OPT["build-option"]) > 1:
            arg_list.append('-Ob')
            for arg in self.ADDITIONAL_OPT["build-option"]:
                arg_list.append(arg)

        subprocess.check_call(arg_list)

    def build_linux(self):
        self.LINUX_DIR = Path.join(self.target_dir, self.THIRD_PARTY_DIR, 'linux')
        self.DT_DIR = Path.join(self.target_dir, self.THIRD_PARTY_DIR, 'litex-devicetree')
        self.BUILDROOT_DIR = Path.join(self.target_dir, self.THIRD_PARTY_DIR, 'buildroot')
        self.LLV_DIR = Path.join(self.target_dir, self.THIRD_PARTY_DIR, 'linux-on-litex-vexriscv')

        # Required settings for default build
        required = ['firmware-url', 'rootfs-url']

        if self.cfg.cpu_variant() != 'linux':
            raise Exception(
                f"Firmware target is linux, but CPU variant is: \
                {self.cfg.cpu_variant()}"
            )
        if self.cfg.cpu_arch() != 'riscv32' and self.cfg.cpu_arch() != 'or1k':
            raise Exception(
                    f"Unsupported CPU arch: {self.cfg.cpu_arch()} for target linux! \
                    Supported: or1k, riscv32"
            )

        if not os.path.exists(self.THIRD_PARTY_DIR):
            os.mkdir(self.THIRD_PARTY_DIR)

        if self.cfg.cpu_arch() == "or1k":
            os.environ["ARCH"] = "openrisc"
        elif self.cfg.cpu_arch() == "riscv32":
            os.environ["ARCH"] = "riscv"

        os.environ["CROSS_COMPILE"] = self.cfg.cpu_arch() + "-linux-musl-"

        for opt in self.LINUX_DEFAULT.keys():
            if opt not in self.cfg._config[self.cfg._default_section].keys():
                if self.firmware_target in self.LINUX_DEFAULT[opt].keys():
                    print(f"No {opt} provided. Using default: {self.LINUX_DEFAULT[opt][self.firmware_target]}")
                    self.ADDITIONAL_OPT[opt] = self.LINUX_DEFAULT[opt][self.firmware_target]
                else:
                    if opt in required:
                        raise Exception("No default value in list {self.LINUX_DEFAULT[opt]} for {self.firmware_target}.")
            else:
                self.ADDITIONAL_OPT[opt] = self.cfg._config[self.cfg._default_section][opt]

        # VexRiscv Emulator TODO
        if self.cfg.cpu() == "vexriscv":
            f = open(Path.join(self.target_dir, 'software', 'include', 'generated', 'mem.h'), 'r')
            insides = f.read()
            f.close()
            emulator_ram_base = re.search('EMULATOR_RAM_BASE.*', insides).group().split(' ')[0][0:-1]
            main_ram_base = re.search('MAIN_RAM_BASE.*', insides).group().split(' ')[0][0:-1]

            emulator_dir = Path.join(os.getcwd(), 'third_party', 'litex',
                'litex', 'soc', 'cores', 'cpu', 'vexriscv', 'verilog', 'ext',
                'VexRiscv', 'src', 'main', 'c', 'emulator')
            emulator_mk = Path.join(emulator_dir, 'makefile')

            os.environ['CFLAGS'] = f"-DDTB={main_ram_base + 0x01000000} -Wl,--defsym,__ram_origin={emulator_ram_base}"
            os.environ['LITEX_BASE'] = self.target_dir
            os.environ['RISCV_BIN'] = f'{self.cfg.cpu_arch()}-elf-newlib-'

            subprocess.check_call(['make', 'clean', '-C', emulator_dir, '-f', f'{emulator_mk}'])
            subprocess.check_call(['make', 'litex', '-C', emulator_dir, '-f', f'{emulator_mk}'])

            # Should call `make clean` equivalent
            # Should call `make litex` equivalent
            # Should copy `emulator.bin` to EMULATOR_BUILD_DIR

        # Download data
        if not os.path.exists(self.LINUX_DIR):
            print(f"Cloning into {self.LINUX_DIR} ...")
            git.Repo.clone_from(self.ADDITIONAL_OPT['firmware-url'],
                self.LINUX_DIR, branch=self.ADDITIONAL_OPT['firmware-branch'],
                progress=Progress())

        if not os.path.exists(self.BUILDROOT_DIR) and 'buildroot' in self.firmware_target:
            print(f"Cloning into {self.BUILDROOT_DIR} ...")
            git.Repo.clone_from(self.ADDITIONAL_OPT['buildroot-url'],
                self.BUILDROOT_DIR, progress=Progress())

        if not os.path.exists(self.LLV_DIR) and self.cfg.cpu() == "vexriscv" and 'buildroot' in self.firmware_target:
            print(f"Cloning into {self.LLV_DIR} ...")
            git.Repo.clone_from(self.ADDITIONAL_OPT['llv-url'],
                self.LLV_DIR, progress=Progress())


        if self.cfg.cpu() == "vexriscv" and 'buildroot' in self.firmware_target:
            # TODO
            print("Linux-Buildroot")
        else:
            print("Linux-LiteX")
            subprocess.check_call(['wget', '-nc', '-P', self.LINUX_DIR, self.ADDITIONAL_OPT['rootfs-url']])
            if not self.ADDITIONAL_OPT['linux-config-url'] == '':
                subprocess.check_call(['wget', '-nc', '-P', Path.join(self.LINUX_DIR, '.config'),
                    self.ADDITIONAL_OPT['linux-config-url']])
                p = subprocess.Popen(["make", "olddefconfig"], cwd=self.LINUX_DIR)
                p.wait()
            else:
                p = subprocess.Popen(["make", "litex_defconfig"], cwd=self.LINUX_DIR)
                p.wait()
            if not self.ADDITIONAL_OPT['dtb-url'] == '':
                subprocess.check_call(['wget', '-nc', '-P', self.LINUX_DIR, self.ADDITIONAL_OPT['dtb-url']])

            if self.cfg.cpu() == "mor1kx":
                os.environ["KERNEL_BINARY"] = "vmlinux.bin"
            elif self.cfg.cpu() == "vexriscv":
                os.environ["KERNEL_BINARY"] = "Image"

            p = subprocess.Popen(["time", "make"], cwd=self.LINUX_DIR)
            p.wait()
            link = Path.join(self.LINUX_DIR, 'arch', os.environ["ARCH"], 'boot', os.environ["KERNEL_BINARY"])
            link_out = os.environ["ARCH"] + "-" + os.environ["KERNEL_BINARY"]
            p = subprocess.Popen([f"ln", "-sf", "{link}", "{link_out}"], cwd=self.LINUX_DIR)
            p.wait()

    functions = { \
    #        'test':run_test, \
    #        'load':run_load, \
    #        'flash':run_flash, \
    #        'connect':run_connect, \
    #        'clear':run_clear, \
            'linux':build_linux, \
    #        'zephyr':build_zephyr, \
    #        'micropython':build_micropython, \
    #        'hdmi2usb':build_hdmi2usb
    }

    def run(self):
        if not os.path.exists(self.target_dir):
            os.mkdir(self.target_dir)
        self.functions[self.firmware](self)

    def __init__(self, firmware, cfg):

        # Additional options which might be present in config
        self.ADDITIONAL_OPT = {
            'firmware-url': str(),
            'firmware-branch': str(),
            'linux-config-url': str(),
            'rootfs-url': str(),
            'dtb-url': str(),
            'buildroot-url': str(),
            'llv-url': str(),
            'tftp-iprange': str(),
            'platform-option': list(),
            'target-option': list(),
            'build-option': list(),
        }

        for opt in self.FIRMWARE_OPT:
            if opt == firmware:
                self.firmware = firmware
                break
        for target in self.FIRMWARE_TARGET:
            if target == firmware:
                self.firmware = firmware
                break
        if self.firmware is None:
            raise Exception(
                "Unsupported --firmware value! Use one of the following: %s"
                % (self.FIRMWARE_OPT + self.IRMWARE_TARGET)
            )

        self.cfg = cfg

        assert self.cfg.cpu_variant() is not None

        # Base firmware_target
        self.firmware_target = f"{self.firmware}-{self.cfg.cpu()}"

        if 'buildroot' in self.cfg._config[self.cfg._default_section].keys():
            if self.cfg._config[self.cfg._default_section]['buildroot'] == 'yes':
                self.firmware_target += "-buildroot"

        full_cpu = self.cfg.cpu()
        if self.cfg.cpu_variant():
            full_cpu = f'{full_cpu}.{self.cfg.cpu_variant()}'

        self.target_dir = Path.join(self.cfg._build_dir,
            f'{self.cfg.platform()}_{self.cfg.target()}_{full_cpu}'
        )

        self.THIRD_PARTY_DIR = Path.join(self.target_dir, 'third_party')


def firmware():
    cfg = config.ConfigManager()
    fm = FirmwareManager(cfg.firmware(), cfg)

    # Build low-level firmware and LiteX related stuff
    fm.build_firmware()
    # Build target software (Linux, Zephyr, FuPy etc.)
    fm.run()
