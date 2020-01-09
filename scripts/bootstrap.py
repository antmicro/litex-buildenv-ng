#!/bin/env/python

import hashlib
import os
import re
import subprocess
import sys
from platform import system
from glob import glob


def get_hash(filename):
    with open(filename, 'rb') as infile:
        data = infile.read()
    return hashlib.sha256(data).hexdigest()


def find_files_recursively(basepath, search_string):
    # Replacement for ' find {basepath} -name {search_string} '
    found_files = []
    for dir, _, files in os.walk(basepath):
        for f in files:
            if f.find(search_string) != -1:
                found_files.append(dir + '/' + f)
    return found_files


def fix_conda():
    for conda_site_package in glob(CONDA_DIR + '/lib/python*/site-packages'):
        conda_common_path = conda_site_package + '/conda/common/path.py'
        if not os.path.exists(conda_common_path):
            continue
        # grep file
        with open(conda_common_path, 'r') as infile:
            for line in infile:
                if re.search('def expanduser', line):
                    print(f"In {conda_site_package} conda/common/path.py is already patched.")
                    continue
        start_sum = get_hash(conda_common_path)
        print(f"In {conda_common_path} ")
        with open(conda_site_package + '/conda/common/path.py', 'r') as infile:
            content_lines = infile.read().split('\n')
        content_lines.insert(49, "def expanduser(path):\n    return expandvars(path.replace('~', '${CONDA_DIR}'))\n\n")
        with open(conda_site_package + '/conda/common/path.py', 'w') as outfile:
            outfile.write('\n'.join(content_lines))
        end_sum = get_hash(conda_common_path)
        if start_sum != end_sum:
            for f in find_files_recursively(CONDA_DIR, 'paths.json'):
                with open(f, 'r') as infile:
                    contents = infile.read()
                contents.replace(start_sum, end_sum)
                with open(f, 'w') as outfile:
                    outfile.write(contents)
        else:
            print("Unable to patch conda path module!")
            exit(1)


def version_equal(tool, desired_version):
    process = subprocess.Popen([f"{tool}", "-V"], stdout=subprocess.PIPE, stderr = subprocess.PIPE)
    out, err = process.communicate();
    out, err = out.decode(), err.decode()
    if err != '' :
        print(f"Calling '{tool} -V' exited with error: {err}")
        return 0
    if out.find(desired_version) != -1:
        print(f"{tool} found at {desired_version}")
        return 1
    else:
        print(f"{tool} (version {desired_version}) NOT found")
        print(f"Calling '{tool} -V' returned: {out}")
        return 0


def pin_conda_package(name, version):
    print(f"Pinning {name} to {version}")
    conda_pin_file = CONDA_DIR + '/conda-meta/pinned'
    pin = f"{name} =={version}"
    if not os.path.exists(conda_pin_file):
        with open(conda_pin_file, 'w') as outfile:
            outfile.write(pin)
    else:
        with open(conda_pin_file, 'r') as infile:
            pinned = infile.read().split("\n")
        found = False
        for line in pinned:
            if line.find(name) != -1:
                line = pin
                found = True
                break
        if not found:
            pinned.insert(0, pin)
        with open(conda_pin_file, 'w') as outfile:
            outfile.write("\n".join(pinned))


def process_call(command_string):
    subprocess.check_call(command_string.split(' '))


if __name__ == "__main__":

    if system() == "Linux":
        if os.path.exists("/lib/udev/rules.d/85-ixo-usb-jtag.rules"):
            print("\tPlease uninstall ixo-usb-jtag package from the timvideos PPA, the" \
                "\trequired firmware is included in the HDMI2SUB modeswitch tool." \
                "\t" \
                "\tOn Debian/Ubuntu run:" \
                "\tsudo apt remove ixo-usb-jtag")
            exit(1)

        if os.path.exists("/etc/udev/rules.d/99-hdmi2usb-permissions.rules") or \
        os.path.exists("/lib/udev/rules.d/99-hdmi2usb-permissions.rules") or    \
        os.path.exists("/lib/udev/rules.d/60-hdmi2usb-udev.rules") or   \
        os.environ.get("HDMI2USB_UDEV_IGNORE") != None :
            pass
        else:
            print("\tPlease install the HDMI2USB udev rules, or 'export HDMI2USB_UDEV_IGNORE=somevalue' to ignore this." \
                "\tFor installation instructions, please see https://github.com/timvideos/litex-buildenv/wiki/HowTo-LCA2018-FPGA-Miniconf#download--setup-udev-rules")
            exit(1)

        if os.environ.get("SETTINGS_FILE") != None or os.environ.get("XILINX") != None :
            print("\tYou appear to have sourced Xilinx ISE settings, these are incompatible with building." \
                "\tPlease exit this terminal and run again from a clean shell")
            exit(1)
    # end if system()

    CONDA_DIR = os.environ.get("CONDA_DIR")
    PYTHON_VERSION = os.environ.get("PYTHON_VERSION")
    CONDA_VERSION = os.environ.get("CONDA_VERSION")
    print("               Pinning conda packages")
    print("---------------------------------------------------")
    fix_conda()
    pin_conda_package('conda', CONDA_VERSION)
    pin_conda_package('python', PYTHON_VERSION)
    print("                 Configuring conda")
    print("---------------------------------------------------")
    process_call(f"conda config --system --add envs_dirs {CONDA_DIR}/envs")
    process_call(f"conda config --system --add pkgs_dirs {CONDA_DIR}/pkgs")
    process_call("conda config --system --set always_yes yes")
    process_call("conda config --system --set changeps1 no")
    process_call("conda update -q conda")

    if not version_equal('python', PYTHON_VERSION):
        exit(1)

    if not version_equal('conda', CONDA_VERSION):
        exit(1)

    fix_conda()
    process_call("conda config --system --add channels timvideos")
    process_call("conda config --system --add channels antmicro")
    process_call("conda info")
    print("           Installing python argh package")
    print("---------------------------------------------------")
    process_call("python -m pip install --upgrade argh")
    print("           Installing python gitpython package")
    print("---------------------------------------------------")
    process_call("python -m pip install --upgrade gitpython")

    print("           Installing OS specific packages")
    print("---------------------------------------------------")

