import click
import types
from gluon.common.particleGenerator.cli import procModel

def dummy():
    pass

def main():
    cli = types.FunctionType(dummy.func_code, {})
    cli = click.group()(cli)
    procModel(cli,
              package_name = "gluon",
              hostenv = "OS_GLUON_HOST",
              portenv = "OS_GLUON_PORT",
              hostdefault = "127.0.0.1",
              portdefault = 2704)
    cli()