import config
import utils
import re
import shutil
import os
import os.path as Path
import git
import wget
import subprocess
from log import Log

class Progress(git.remote.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print('update(%s, %s, %s)' % (cur_count, max_count, message))

class FirmwareManager:

    FIRMWARE_OPT = ['test', 'load', 'flash', 'connect', 'clear']
    FIRMWARE_TARGET = ['linux', 'zephyr', 'micropython', 'hdmi2usb']

    # Default remotes if FIRMWARE_URL, FIRMWARE_BRANCH, ROOTFS_URL etc. are not provided

    # Linux URL:
    LINUX = { \
        'linux-mor1kx':'https://github.com/timvideos/linux-litex.git', \
        'linux-vexriscv':'https://github.com/timvideos/linux-litex.git', \
        'linux-vexriscv-buildroot':'https://github.com/torvalds/linux.git'
    }
    LINUX_BRANCH = { \
        'linux-mor1kx':'master-litex', \
        'linux-vexriscv':'master-litex', \
        'linux-vexriscv-buildroot':'v5.0'
    }
    # Specific defconfig:
    LINUX_DEFCONFIG = { \
        'linux-vexriscv':'https://antmicro.com/projects/renode/litex-buildenv/litex_vexriscv_linux.config'
    }
    # Rootfs URL:
    ROOTFS = { \
        'linux-mor1kx':"https://ozlabs.org/~joel/openrisc-rootfs.cpio.gz", \
        'linux-vexriscv':"https://antmicro.com/projects/renode/litex-buildenv/riscv32-rootfs.cpio", \
        'linux-vexriscv-buildroot':"https://antmicro.com/projects/renode/litex-buildenv/riscv32-rootfs.cpio"
    }
    # Ready to use dtbs:
    DTB = { \
        'linux-vexriscv':"https://antmicro.com/projects/renode/litex-buildenv/rv32.dtb"
    }
    # Buildroot URL:
    BUILDROOT = { \
        'linux-vexriscv-buildroot':"https://github.com/buildroot/buildroot.git"
    }
    # Vexriscv specific Linux for Buildroot target
    LLV = { \
        'linux-vexriscv-buildroot':"https://github.com/litex-hub/linux-on-litex-vexriscv.git"
    }

    def build_linux(self):
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

        target = 'linux-' + self.cfg.cpu()
        if self.cfg.cpu_arch() == "or1k":
            os.environ["ARCH"] = "openrisc"
        elif self.cfg.cpu_arch() == "riscv32":
            os.environ["ARCH"] = "riscv"

        if self.cfg._build_buildroot != None:
            target = target + '-buildroot'
        os.environ["CROSS_COMPILE"] = self.cfg.cpu_arch() + "-linux-musl-"

        if self.cfg._firmware_url == None:
            if target in self.LINUX.keys():
                print(f"No FIRMWARE_URL provided. Using default: {self.LINUX[target]}")
                self.firmware_url = self.LINUX[target]
            else:
                raise Exception("No default Linux for {target}.")
        else:
            self.firmware_url = self.cfg._firmware_url

        if self.cfg._firmware_branch == None:
            if target in self.LINUX_BRANCH.keys():
                print(f"No FIRMWARE_BRANCH provided. Using default: {self.LINUX_BRANCH[target]}")
                self.firmware_branch = self.LINUX_BRANCH[target]
        else:
            self.firmware_branch = self.cfg._firmware_branch

        if self.cfg._rootfs_url == None:
            if target in self.ROOTFS.keys():
                print(f"No ROOTFS_URL provided. Using default: {self.ROOTFS[target]}")
                self.rootfs_url = self.ROOTFS[target]
            else:
                raise Exception("No default Rootfs for {target}.")
        else:
            self.rootfs_url = self.cfg._rootfs_url

        if self.cfg._dtb_url == None:
            if target in self.DTB.keys():
                print(f"No DTB_URL provided. Using default: {self.DTB[target]}")
                self.dtb_url = self.DTB[target]
            else:
                print("[WARN] No default Device tree for {target}.")
        else:
            self.dtb_url = self.cfg._dtb_url

        if self.cfg._buildroot_url == None and self.cfg._build_buildroot != None:
            if target in self.BUILDROOT.keys():
                print(f"No BUILDROOT_URL provided. Using default: {self.BUILDROOT[target]}")
                self.buildroot_url = self.BUILDROOT[target]
        elif self.cfg._build_buildroot != None:
            self.buildroot_url = self.cfg._buildroot_url

        if self.cfg._llv_url == None and self.cfg.cpu() == "vexriscv" and self.cfg._build_buildroot != None:
            if target in self.LLV.keys():
                print(f"No LLV_URL provided. Using default: {self.LLV[target]}")
                self.llv_url = self.LLV[target]
        elif self.cfg.cpu() == "vexriscv" and self.cfg._build_buildroot != None:
            self.llv_url = self.cfg._llv_url

        # Download data
        if not os.path.exists(self.LINUX_DIR):
            print(f"Cloning into {self.LINUX_DIR} ...")
            git.Repo.clone_from(self.firmware_url, self.LINUX_DIR, branch=self.firmware_branch, progress=Progress())

        if not os.path.exists(self.BUILDROOT_DIR) and self.cfg._build_buildroot != None:
            print(f"Cloning into {self.BUILDROOT_DIR} ...")
            git.Repo.clone_from(self.buildroot_url, self.BUILDROOT_DIR, progress=Progress())

        if not os.path.exists(self.LLV_DIR) and self.cfg.cpu() == "vexriscv" and self.cfg._build_buildroot != None:
            print(f"Cloning into {self.LLV_DIR} ...")
            git.Repo.clone_from(self.llv_url, self.LLV_DIR, progress=Progress())

        # VexRiscv Emulator
        if self.cfg.cpu() == "vexriscv":
            print("Should build VexRiscV emulator")
            # Should call `make firmware` equivalent
            # Should call `make clean` equivalent
            # Should call `make litex` equivalent
            # Should copy `emulator.bin` to EMULATOR_BUILD_DIR

	#GENERATED_JSON="$TARGET_BUILD_DIR/test/csr.json"
	#if [ ! -f "$GENERATED_JSON" ]; then
	#	make firmware
	#fi

        if self.cfg.cpu() == "vexriscv" and self.cfg._build_buildroot != None:
            print("Vex + Buildroot")
        else:
            print("Linux-LiteX")
            print(os.getcwd())
            wget.download(self.rootfs_url, self.LINUX_DIR)
            if target in self.LINUX_DEFCONFIG.keys():
                wget.download(self.LINUX_DEFCONFIG[target], Path.join(self.LINUX_DIR, '.config'))
                p = subprocess.Popen(["make", "olddefconfig"], cwd=self.LINUX_DIR)
                p.wait()
            else:
                p = subprocess.Popen(["make", "litex_defconfig"], cwd=self.LINUX_DIR)
                p.wait()
            if target in self.DTB.keys():
                wget.download(self.DTB[target], Path.join(self.LINUX_DIR))

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
        if not os.path.exists('third-party'):
            os.mkdir('third-party')
        self.functions[self.firmware](self)

    def __init__(self, firmware, cfg):
        for opt in self.FIRMWARE_OPT:
            if opt == firmware:
                self.firmware = firmware
                break
        for target in self.FIRMWARE_TARGET:
            if target == firmware:
                self.firmware = firmware
                break
        if self.firmware == None:
            raise Exception(
                "Unsupported --firmware value! Use one of the following: %s" \
                % (FIRMWARE_OPT + FIRMWARE_TARGET)
            )
        self.cfg = cfg
        self.top_dir = self.cfg._build_dir

        self.LINUX_DIR = Path.join(self.top_dir, 'third_party', 'linux')
        self.DT_DIR = Path.join(self.top_dir, 'third_party', 'litex-devicetree')
        self.BUILDROOT_DIR = Path.join(self.top_dir, 'third_party', 'buildroot')
        self.LLV_DIR = Path.join(self.top_dir, 'third_party', 'linux-on-litex-vexriscv')



def firmware():
    cfg = config.ConfigManager()
    fm = FirmwareManager(cfg.firmware(), cfg)

    fm.run()
