import os
import os.path as Path
import subprocess

LITE_REPOS=[
    "migen",
    "nmigen",
    "litex",
    "litedram",
    "liteeth",
    "litepcie",
    "litesata",
    "litescope",
    "litevideo"
]

if __name__ == '__main__':
    for repo in LITE_REPOS:
        setup_path = Path.join(os.getcwd(), 'third_party', repo, 'setup.py')
        setup_dir = Path.join(os.getcwd(), 'third_party', repo)
        if not Path.exists(setup_path):
            print(f'Path: {setup_path} does not exists.\
                    Do you run script from repo root directory?')
        else:
            subprocess.check_call(['python3', setup_path, 'develop'],
                                  cwd=setup_dir)
