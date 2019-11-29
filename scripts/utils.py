import subprocess
import importlib
import importlib.util
import sys
import os
from log import Log
import io
import contextlib
import os.path as Path


def create_symlink(source, destination):
    if Path.exists(destination):
        real_target = os.readlink(destination)
        if real_target != source:
            raise Exception(
                f"Cannot install {source}, as the target symlink {destination} exists and points to {real_target}"
            )
    else:
        os.symlink(source, destination)


def get_python_module_version(module_name):
    module = importlib.import_module(module_name)
    return module.__version__


def get_program_version(program):
    return subprocess.run([program, '--version'],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT).stdout.decode('utf-8')


def run_python_module_log_output(name, module_path, tools_dir):
    # no try/except - we want to fail if it doesn't work
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "setup"):
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                module.setup(tools_dir)
            Log.log(output.getvalue())
        except Exception as e:
            Log.log(e)
            raise

    else:
        raise Exception(
            f"Module {module_path} does not implement `setup` function")


def run_process_log_output(params):
    log = ""
    process = subprocess.Popen(params,
                               stderr=subprocess.STDOUT,
                               stdout=subprocess.PIPE)

    while True:
        output = process.stdout.readline()

        if output == b'' and process.poll() is not None:
            break
        if output:
            log += output.decode(sys.stdout.encoding)
    Log.log(log)

    if process.poll() != 0:
        raise Exception(
            f"Command '{' '.join(params)}' exited with code {process.poll()}")

    return process.poll() == 0
