import config
import sys
import os
import os.path as Path
import git
import re
import subprocess
import requests
import shutil
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
    ZEPHYR = {
        'zephyr-vexriscv': 'https://github.com/zephyrproject-rtos/zephyr.git',
    }

    ZEPHYR_BRANCH = {
        'zephyr-vexriscv': 'master',
    }

    ZEPHYR_SDK = {
        'zephyr-vexriscv': 'https://github.com/zephyrproject-rtos/sdk-ng/releases/latest',
    }

    ZEPHYR_SDK_DIR = {
        'zephyr-vexriscv': 'third_party/zephyr-sdk',
    }

    ZEPHYR_DEFAULT = {
        'firmware-url': ZEPHYR,
        'firmware-branch': ZEPHYR_BRANCH,
        'zephyr-sdk-url': ZEPHYR_SDK,
        'zephyr-sdk-dir': ZEPHYR_SDK_DIR,
        'zephyr-app': {},
    }

    # FuPy defaults:
    FUPY = {
        'micropython-vexriscv': 'https://github.com/fupy/micropython.git',
        'micropython-mor1kx': 'https://github.com/fupy/micropython.git',
        'micropython-lm32': 'https://github.com/fupy/micropython.git',
    }

    FUPY_BRANCH = {
        'micropython-vexriscv': 'master',
        'micropython-mor1kx': 'master',
        'micropython-lm32': 'master',
    }

    FUPY_DEFAULT = {
        'firmware-url': FUPY,
        'firmware-branch': FUPY_BRANCH,
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
                self.ADDITIONAL_OPT[opt] = \
                    self.cfg._config[self.cfg._default_section][opt]

        arg_list = ['python', 'scripts/make.py',
                    '--platform',
                    self.cfg.platform(),
                    '--target',
                    self.cfg.target(),
                    '--cpu-type',
                    self.cfg.cpu(),
                    '--iprange',
                    self.ADDITIONAL_OPT["tftp-iprange"],
                    '--no-compile-gateware']

        if not self.cfg.cpu_variant() == None:
            arg_list.append('--cpu-variant')
            arg_list.append(self.cfg.cpu_variant())

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

    def build_micropython(self):
        required = ['firmware-url']
        litex_files = ['system.h', 'csr-defs.h', 'spr-defs.h']
        litex_base = Path.join(os.getcwd(), 'third_party', 'litex', 'litex',
                               'soc', 'software', 'include', 'base')

        for f in litex_files:
            shutil.copyfile(Path.join(litex_base, f),
                            Path.join(self.target_dir, 'software', 'include', f))

        for opt in self.FUPY_DEFAULT.keys():
            if opt not in self.cfg._config[self.cfg._default_section].keys():
                if self.firmware_target in self.FUPY_DEFAULT[opt].keys():
                    print(f'No {opt} provided. Using default:'
                          f'{self.FUPY_DEFAULT[opt][self.firmware_target]}')
                    self.ADDITIONAL_OPT[opt] = \
                        self.FUPY_DEFAULT[opt][self.firmware_target]
                else:
                    if opt in required:
                        raise Exception('No default value for option '
                                        f'{opt} for target '
                                        f'{self.firmware_target}.')
            else:
                self.ADDITIONAL_OPT[opt] = \
                    self.cfg._config[self.cfg._default_section][opt]

        # Download Micro Python
        if not os.path.exists(self.FIRMWARE_DIR):
            print(f"Cloning into {self.FIRMWARE_DIR} ...")
            r = git.Repo.clone_from(self.ADDITIONAL_OPT['firmware-url'],
                                    self.FIRMWARE_DIR,
                                    branch=self.ADDITIONAL_OPT['firmware-branch'],
                                    progress=Progress())

            for submodule in r.submodules:
                submodule.update(init=True)

        micropython_build_dir = Path.join(self.target_dir, 'software', 'micropython')
        micropython_inc_dir = Path.join(self.target_dir, 'software', 'include')
        if not os.path.exists(micropython_build_dir):
            os.mkdir(micropython_build_dir)
            subprocess.check_call(['ln', '-s', Path.join(micropython_inc_dir,
                                                         'generated'),
                                   'generated'],
                                  cwd=micropython_build_dir)

        os.environ['CROSS_COMPILE'] = f'{self.cfg.cpu_arch()}-elf-'
        os.environ['BUILDINC_DIRECTORY'] = micropython_inc_dir
        os.environ['BUILD'] = micropython_build_dir

        subprocess.check_call(['make', 'V=1',
                               f'-j{str(self.ADDITIONAL_OPT["jobs"])}',
                               '-C', f'{Path.join(self.FIRMWARE_DIR, "ports", "fupy")}'])

    def build_zephyr(self):
        supported_variants = ['lite', 'full', 'standard', 'linux']
        if not self.cfg.cpu() == "vexriscv":
            raise Exception(f'Unsupported CPU: {self.cfg.cpu()} '
                            'for firmware Zephyr! Supported: vexriscv')
        if not self.cfg.cpu_variant() in supported_variants:
            raise Exception(
                f'Zephyr firmware needs CPU variant {supported_variants}, but given is: '
                f'{self.cfg.cpu_variant()}'
            )

        target_board = f'litex_{self.cfg.cpu()}'

        # Required settings for default build
        required = ['firmware-url', 'zephyr-sdk-dir', 'zephyr-app']

        if not os.path.exists(self.THIRD_PARTY_DIR):
            os.mkdir(self.THIRD_PARTY_DIR)

        for opt in self.ZEPHYR_DEFAULT.keys():
            if opt not in self.cfg._config[self.cfg._default_section].keys():
                if self.firmware_target in self.ZEPHYR_DEFAULT[opt].keys():
                    print(f'No {opt} provided. Using default:'
                          f'{self.ZEPHYR_DEFAULT[opt][self.firmware_target]}')
                    self.ADDITIONAL_OPT[opt] = \
                        self.ZEPHYR_DEFAULT[opt][self.firmware_target]
                else:
                    if opt in required:
                        raise Exception('No default value for option '
                                        f'{opt} for target '
                                        f'{self.firmware_target}.')
            else:
                self.ADDITIONAL_OPT[opt] = \
                    self.cfg._config[self.cfg._default_section][opt]

        if self.ADDITIONAL_OPT['zephyr-sdk-local'] == 'yes':
            zephyr_sdk_dir = self.ADDITIONAL_OPT['zephyr-sdk-dir']
        else:
            zephyr_sdk_dir = Path.join(self.target_dir,
                                       self.ADDITIONAL_OPT['zephyr-sdk-dir'])

        output_dir = Path.join(self.target_dir, 'software', 'zephyr')

        # Download data
        if not os.path.exists(self.FIRMWARE_DIR):
            os.mkdir(self.FIRMWARE_DIR)
            print(f"West init in {self.FIRMWARE_DIR} ...")
            subprocess.check_call(['west', 'init', '--manifest-url',
                                   self.ADDITIONAL_OPT['firmware-url'],
                                   '--manifest-rev',
                                   self.ADDITIONAL_OPT['firmware-branch']],
                                  cwd=self.FIRMWARE_DIR)
            subprocess.check_call(['west', 'update'], cwd=self.FIRMWARE_DIR)

        if not os.path.exists(zephyr_sdk_dir):
            if not self.ADDITIONAL_OPT['zephyr-sdk-local'] == 'yes':
                r = requests.get(self.ADDITIONAL_OPT['zephyr-sdk-url'])
                url = r.url
                sdk_version = url.split('/')[-1][1:]
                sdk_url = f'{url.replace("tag", "download")}/zephyr-sdk-{sdk_version}-setup.run'
                print(f"Downloading Zephyr SDK {sdk_version} to {self.THIRD_PARTY_DIR} ...")
                subprocess.check_call(['wget', '-nc', '-P',
                                       self.THIRD_PARTY_DIR, sdk_url])
                sdk = Path.join(self.THIRD_PARTY_DIR,
                                f'zephyr-sdk-{sdk_version}-setup.run')
                subprocess.check_call(['chmod', 'u+x', sdk])
                subprocess.check_call([sdk, '--', '-y', '-d', zephyr_sdk_dir])
            else:
                raise Exception(f"Zephyr SDK not found in {zephyr_sdk_dir}")

        os.environ['ZEPHYR_BASE'] = Path.join(self.FIRMWARE_DIR, 'zephyr')
        os.environ['ZEPHYR_SDK_INSTALL_DIR'] = zephyr_sdk_dir
        os.environ['ZEPHYR_TOOLCHAIN_VARIANT'] = 'zephyr'

        subprocess.check_call(['west', 'build', '-b', target_board,
                              Path.join(os.environ['ZEPHYR_BASE'], 'samples',
                                        self.ADDITIONAL_OPT['zephyr-app']),
                               '--build-dir', output_dir, '--',
                               f'-DZEPHYR_SDK_INSTALL_DIR={zephyr_sdk_dir}'])

        subprocess.check_call(['ln', '-s', Path.join(output_dir,
                               'zephyr', 'zephyr.bin'),
                               Path.join(output_dir, 'firmware.bin')])

    def build_linux(self):
        DT_DIR = Path.join(self.target_dir,
                           self.THIRD_PARTY_DIR, 'litex-devicetree')
        BUILDROOT_DIR = Path.join(self.target_dir,
                                  self.THIRD_PARTY_DIR, 'buildroot')
        LLV_DIR = Path.join(self.target_dir, self.THIRD_PARTY_DIR,
                            'linux-on-litex-vexriscv')

        # Required settings for default build
        required = ['firmware-url', 'rootfs-url']

        if self.cfg.cpu_variant() != 'linux':
            raise Exception(
                f'Firmware target is linux, but CPU variant is:'
                f'{self.cfg.cpu_variant()}'
            )
        if self.cfg.cpu_arch() != 'riscv32' and self.cfg.cpu_arch() != 'or1k':
            raise Exception(
                    f'Unsupported CPU arch: {self.cfg.cpu_arch()} for'
                    'firmware linux! Supported: or1k, riscv32'
            )

        if not os.path.exists(self.THIRD_PARTY_DIR):
            os.mkdir(self.THIRD_PARTY_DIR)

        if self.cfg.cpu_arch() == "or1k":
            os.environ["ARCH"] = "openrisc"
        elif self.cfg.cpu_arch() == "riscv32":
            os.environ["ARCH"] = "riscv"

        os.environ["CROSS_COMPILE"] = f'{self.cfg.cpu_arch()}-linux-musl-'

        for opt in self.LINUX_DEFAULT.keys():
            if opt not in self.cfg._config[self.cfg._default_section].keys():
                if self.firmware_target in self.LINUX_DEFAULT[opt].keys():
                    print(f'No {opt} provided. Using default:'
                          f'{self.LINUX_DEFAULT[opt][self.firmware_target]}')
                    self.ADDITIONAL_OPT[opt] = \
                        self.LINUX_DEFAULT[opt][self.firmware_target]
                else:
                    if opt in required:
                        raise Exception('No default value in list'
                                        f'{self.LINUX_DEFAULT[opt]} for'
                                        f'{self.firmware_target}.')
            else:
                self.ADDITIONAL_OPT[opt] = \
                    self.cfg._config[self.cfg._default_section][opt]

        # VexRiscv Emulator TODO
        if self.cfg.cpu() == "vexriscv":
            f = open(Path.join(self.target_dir, 'software', 'include',
                               'generated', 'mem.h'), 'r')
            insides = f.read()
            f.close()
            emulator_ram_base = re.search('EMULATOR_RAM_BASE.*',
                                          insides).group().split(' ')[0][0:-1]
            main_ram_base = re.search('MAIN_RAM_BASE.*',
                                      insides).group().split(' ')[0][0:-1]

            emulator_dir = Path.join(os.getcwd(), 'third_party', 'litex',
                                     'litex', 'soc', 'cores', 'cpu',
                                     'vexriscv', 'verilog', 'ext',
                                     'VexRiscv', 'src', 'main', 'c',
                                     'emulator')
            emulator_mk = Path.join(emulator_dir, 'makefile')

            os.environ['CFLAGS'] = f"-DDTB={main_ram_base + 0x01000000} -Wl,\
                                     --defsym,__ram_origin={emulator_ram_base}"
            os.environ['LITEX_BASE'] = self.target_dir
            os.environ['RISCV_BIN'] = f'{self.cfg.cpu_arch()}-elf-'

            subprocess.check_call(['make', 'clean', '-C', emulator_dir,
                                   '-f', f'{emulator_mk}'])
            subprocess.check_call(['make', 'litex', '-C', emulator_dir,
                                   '-f', f'{emulator_mk}'])

            # Should copy `emulator.bin` to EMULATOR_BUILD_DIR

        # Download data
        if not os.path.exists(self.FIRMWARE_DIR):
            print(f"Cloning into {self.FIRMWARE_DIR} ...")
            git.Repo.clone_from(self.ADDITIONAL_OPT['firmware-url'],
                                self.FIRMWARE_DIR,
                                branch=self.ADDITIONAL_OPT['firmware-branch'],
                                progress=Progress())

        if not os.path.exists(BUILDROOT_DIR) \
                and 'buildroot' in self.firmware_target:
            print(f"Cloning into {self.BUILDROOT_DIR} ...")
            git.Repo.clone_from(self.ADDITIONAL_OPT['buildroot-url'],
                                BUILDROOT_DIR, progress=Progress())

        if not os.path.exists(LLV_DIR) \
                and self.cfg.cpu() == "vexriscv" \
                and 'buildroot' in self.firmware_target:
            print(f"Cloning into {self.LLV_DIR} ...")
            git.Repo.clone_from(self.ADDITIONAL_OPT['llv-url'],
                                LLV_DIR, progress=Progress())

        if self.cfg.cpu() == "vexriscv" \
                and 'buildroot' in self.firmware_target:
            # TODO
            print("Linux-Buildroot")
        else:
            print("Linux-LiteX")
            subprocess.check_call(['wget', '-nc', '-P', self.FIRMWARE_DIR,
                                   self.ADDITIONAL_OPT['rootfs-url']])
            if not self.ADDITIONAL_OPT['linux-config-url'] == '':
                subprocess.check_call(['wget', '-nc', '-P',
                                       Path.join(self.FIRMWARE_DIR, '.config'),
                                       self.ADDITIONAL_OPT['linux-config-url']])
                subprocess.check_call(['make', 'olddefconfig'],
                                      cwd=self.FIRMWARE_DIR)
            else:
                subprocess.check_call(['make', 'litex_defconfig'],
                                      cwd=self.FIRMWARE_DIR)
            if not self.ADDITIONAL_OPT['dtb-url'] == '':
                subprocess.check_call(['wget', '-nc', '-P', self.FIRMWARE_DIR,
                                       self.ADDITIONAL_OPT['dtb-url']])

            if self.cfg.cpu() == "mor1kx":
                os.environ["KERNEL_BINARY"] = "vmlinux.bin"
            elif self.cfg.cpu() == "vexriscv":
                os.environ["KERNEL_BINARY"] = "Image"

            subprocess.check_call(['make', f'-j{str(self.ADDITIONAL_OPT["jobs"])}'],
                                  cwd=self.FIRMWARE_DIR)
            link = Path.join(self.FIRMWARE_DIR, 'arch', os.environ["ARCH"],
                             'boot', os.environ["KERNEL_BINARY"])
            link_out = Path.join(self.FIRMWARE_DIR,
                                 f'{os.environ["ARCH"]}-'
                                 f'{os.environ["KERNEL_BINARY"]}')
            subprocess.check_call(["ln", "-sf", f"{link}", f"{link_out}"],
                                  cwd=self.FIRMWARE_DIR)

    functions = {
        'linux': build_linux,
        'zephyr': build_zephyr,
        'micropython': build_micropython
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
            'zephyr-sdk-url': str(),
            'zephyr-sdk-dir': str(),
            'zephyr-sdk-local': str(),
            'zephyr-app': str(),
            'jobs': int(),
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

        if 'jobs' in self.cfg._config[self.cfg._default_section].keys():
            self.ADDITIONAL_OPT['jobs'] = \
                int(self.cfg._config[self.cfg._default_section]['jobs'])
        else:
            self.ADDITIONAL_OPT['jobs'] = 1

        # Base firmware_target
        self.firmware_target = f"{self.firmware}-{self.cfg.cpu()}"

        if 'buildroot' in self.cfg._config[self.cfg._default_section].keys():
            if self.cfg._config[self.cfg._default_section]['buildroot'] == 'yes':
                self.firmware_target += "-buildroot"

        full_cpu = self.cfg.cpu()
        if self.cfg.cpu_variant():
            full_cpu = f'{full_cpu}.{self.cfg.cpu_variant()}'

        self.target_dir = Path.join(self.cfg._build_dir,
                                    f'{self.cfg.platform()}_'
                                    f'{self.cfg.target()}_{full_cpu}')

        self.THIRD_PARTY_DIR = Path.join(self.target_dir, 'third_party')
        self.FIRMWARE_DIR = Path.join(self.THIRD_PARTY_DIR,
                                      self.cfg.firmware())


def firmware():
    cfg = config.ConfigManager()
    fm = FirmwareManager(cfg.firmware(), cfg)

    try:
        if not cfg.firmware() == 'zephyr':
            fm.build_firmware()
    except Exception as e:
        print(e)
        sys.exit(1)

    try:
        if not cfg.firmware() == 'hdmi2usb':
            fm.run()
    except Exception as e:
        print(e)
        sys.exit(1)
