# LiteX BuildEnv NG (working title)

This project is intended to supersede [the original LiteX BuildEnv](https://github.com/timvideos/litex-buildenv).

Presently called “LiteX BuildEnv NG”, it is aimed to be multiplatform, more Pythonic and solve some other issues which became apparent throughout the lifetime of LBE.

The tool can be used in a similar way to the original LiteX BuildEnv: to prepare a shell environment the user has to source the `./bootstrap.sh` script, providing relevant CLI parameters or using the configuration file.

More documentation is obviously on its way.

## Dockerized dependency feature

One of the new features of the "NG" version of LBE is the ability to deliver dockerized dependencies locally instead of downloading and building them.

To indicate that a tool mentioned in the `./requirements/` subdirectory will be delivered locally, the user must fill the `local-tools.env` configuration file. The format is as follows:

```
[tool-name] # without any additional info, the tool is assumed to be available in PATH

[tool-name]
path = /path/to/file # a symlink to the provided file is created in build/bin subdirectory

[tool-name]
path = /path/to/dir # symlinks to all files in dir are created

[tool-name]
script = /path/to/script.sh # the script is called with path to build/bin as an argument, and is expected to install necessary files there

[tool-name]
python = /path/to/python.py # the python module is loaded in the same process, and a "setup” function is called, with path to build/bin as an argument.
```

A way to use Docker images as tool backends is currently implemented for three sample tools: flterm, openocd and renode.

The image definitions and related scripts, compatible with LiteX BuildEnv NG, are available [on GitHub](https://github.com/antmicro/litex-buildenv-ng-docker-backends/).

For each tool, a Python script is created, with a `setup` function. It should be called with a path to which it should install the runner scripts.

The runner scripts are OS-specific and it's up to the user to provide versions compliant with the system used.
