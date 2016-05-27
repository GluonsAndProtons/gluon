import click
import types
from gluon.common.particleGenerator.cli import procModel

def dummy():
    pass

def main():
    cli = types.FunctionType(dummy.func_code, {})
    cli = click.group()(cli)
    procModel(cli,
              package_name = "proton",
              hostenv = "OS_PROTON_HOST",
              portenv = "OS_PROTON_PORT",
              hostdefault = "127.0.0.1",
              portdefault = 2705)
    cli()
