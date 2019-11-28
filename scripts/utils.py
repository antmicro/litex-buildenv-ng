import subprocess
import importlib
import sys


def get_python_module_version(module_name):
    module = importlib.import_module(module_name)
    return module.__version__


def get_program_version(program):
    return subprocess.run([program, '--version'],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT).stdout.decode('utf-8')


def run_process_print_output(params):
    process = subprocess.Popen(params,
                               stderr=subprocess.STDOUT,
                               stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output == b'' and process.poll() is not None:
            break
        if output:
            print(output.decode(sys.stdout.encoding).strip("\n\r"))

    return process.poll() == 0
