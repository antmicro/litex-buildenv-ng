#!/usr/bin/env python3

import argh
from prepare import prepare
from gateware import gateware
from firmware import firmware

def prepare():
    print("Hello")

if __name__ == '__main__':
    parser = argh.ArghParser()
    parser.add_argument("-e", "--env", action="store", default="default", help="Custom environment name")
    parser.add_argument("--cpu", help="cpu name")
    parser.add_argument("--cpu-variant", help="cpu variant")
    parser.add_argument("--platform", help="platform name")
    parser.add_argument("--target", help="setup type")
    parser.add_argument("--firmware", help="target firmware")
    parser.add_commands([
        prepare,
        gateware,
        firmware
    ])
    parser.dispatch()


