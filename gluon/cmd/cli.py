import click
import types
import json
import gluon.common.particleGenerator.cli as cligen

def dummy():
    pass

def make_a_func(operation, tablename, primary_key):
    def update_func(**kwargs):
        url = cligen.make_url(kwargs["host"], kwargs["port"], tablename, kwargs[primary_key],operation)
        del kwargs["host"]
        del kwargs["port"]
        del kwargs[primary_key]
        data = {}
        for key, val in kwargs.iteritems():
            if val is not None:
                data[key] = val
        result = cligen.do_put(url, data)
        print json.dumps(result, indent=4)
    return update_func

def add_extensions(cli, package_name = "gluon",
                        hostenv = "OS_GLUON_HOST",
                        portenv = "OS_GLUON_PORT",
                        hostdefault = "127.0.0.1",
                        portdefault = 2704):
    attributes = {}
    attributes["device_owner"] = {'description': 'Name of compute or network service',
                                  'type': 'string', 'required': True}
    attributes["device_id"] = {'description': 'UUID of bound VM', 'type': 'string',
                               'required': True}
    attributes["host_id"] = {'description': 'binding:host_id: Name of bound host', 'type': 'string',
                             'required': True}
    attributes["zone"] = {'description': 'Zone information', 'type': 'string'}
    hosthelp = "Host of endpoint (%s) " % hostenv
    porthelp = "Port of endpoint (%s) " % portenv
    #
    # Add bind
    #
    update = make_a_func('bind', 'ports', 'id')
    update.func_name = "%s-bind" % ('port')
    update = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(update)
    update = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(update)
    for col_name, col_desc in attributes.iteritems():
        kwargs = {}
        option_name = "--" + col_name
        required = col_desc.get('required', False)
        if required:
            kwargs["required"] = True
        kwargs["default"] = None
        kwargs["help"] = col_desc.get('description', "no description")
        cligen.set_type(kwargs, col_desc)
        update = click.option(option_name, **kwargs)(update)
    update = click.argument('id')(update)
    cli.command()(update)
    #
    # Add unbind
    #
    update = make_a_func('unbind', 'ports', 'id')
    update.func_name = "%s-unbind" % ('port')
    update = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(update)
    update = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(update)
    update = click.argument('id')(update)
    cli.command()(update)

def main():
    cli = types.FunctionType(dummy.func_code, {})
    cli = click.group()(cli)
    cligen.procModel(cli,
              package_name = "gluon",
              hostenv = "OS_GLUON_HOST",
              portenv = "OS_GLUON_PORT",
              hostdefault = "127.0.0.1",
              portdefault = 2704)
    add_extensions(cli)
    cli()