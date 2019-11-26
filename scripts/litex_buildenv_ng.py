#!/usr/bin/env python3

import argh

def prepare():
    print("Hello")

if __name__ == '__main__':
    parser = argh.ArghParser()
    parser.add_commands([
        prepare,
        gateware,
        firmware
    ])
    parser.dispatch()


