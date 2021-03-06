import pkg_resources
import yaml
import click
from gluon.common import exception as exc
from requests import get, put, post, delete
import json


def load_model(package_name):
    model = {}
    for f in pkg_resources.resource_listdir(package_name, 'models'):
        f = "models/" + f
        with pkg_resources.resource_stream(package_name, f) as fd:
            model.update(yaml.safe_load(fd))
    return model


def json_get(url):
    resp = get(url)
    if resp.status_code != 200:
        raise exc.GluonClientException('Bad return status %d'
                                       % resp.status_code,
                                       status_code=resp.status_code)
    try:
        rv = json.loads(resp.content)
    except Exception as e:
        raise exc.MalformedResponseBody(reason="JSON unreadable: %s on %s"
                                               % (e.message, resp.content))
    return rv


def do_delete(url):
    resp = delete(url)
    if resp.status_code != 200 and resp.status_code != 204:
        raise exc.GluonClientException('Bad return status %d'
                                       % resp.status_code,
                                       status_code=resp.status_code)


def do_post(url, values):
    resp = post(url, json=values)
    if resp.status_code != 200 and resp.status_code != 201:
        raise exc.GluonClientException('Bad return status %d'
                                       % resp.status_code,
                                       status_code=resp.status_code)
    try:
        rv = json.loads(resp.content)
    except Exception as e:
        raise exc.MalformedResponseBody(reason="JSON unreadable: %s on %s"
                                               % (e.message, resp.content))
    return rv


def do_put(url, values):
    resp = put(url, json=values)
    if resp.status_code != 200:
        raise exc.GluonClientException('Bad return status %d'
                                       % resp.status_code,
                                       status_code=resp.status_code)
    try:
        rv = json.loads(resp.content)
    except Exception as e:
        raise exc.MalformedResponseBody(reason="JSON unreadable: %s on %s"
                                               % (e.message, resp.content))
    return rv


def make_url(host, port, *args):
    url = "http://%s:%d/v1" % (host, port)
    for arg in args:
        url = "%s/%s" % (url, arg)
    return url


def make_list_func(tablename):
    def list_func(**kwargs):
        url = make_url(kwargs["host"], kwargs["port"], tablename)
        result = json_get(url)
        print json.dumps(result, indent=4)

    return list_func


def make_show_func(tablename, primary_key):
    def show_func(**kwargs):
        url = make_url(kwargs["host"], kwargs["port"], tablename, kwargs[primary_key])
        result = json_get(url)
        print json.dumps(result, indent=4)

    return show_func


def make_create_func(tablename):
    def create_func(**kwargs):
        url = make_url(kwargs["host"], kwargs["port"], tablename)
        del kwargs["host"]
        del kwargs["port"]
        data = {}
        for key, val in kwargs.iteritems():
            if val is not None:
                data[key] = val
        result = do_post(url, data)
        print json.dumps(result, indent=4)

    return create_func


def make_update_func(tablename, primary_key):
    def update_func(**kwargs):
        url = make_url(kwargs["host"], kwargs["port"], tablename, kwargs[primary_key], "update")
        del kwargs["host"]
        del kwargs["port"]
        del kwargs[primary_key]
        data = {}
        for key, val in kwargs.iteritems():
            if val is not None:
                data[key] = val
        result = do_put(url, data)
        print json.dumps(result, indent=4)

    return update_func


def make_delete_func(tablename, primary_key):
    def delete_func(**kwargs):
        url = make_url(kwargs["host"], kwargs["port"], tablename, kwargs[primary_key])
        do_delete(url)

    return delete_func


def get_primary_key(table_data):
    primary = []
    for k, v in table_data['attributes'].iteritems():
        if 'primary' in v:
            primary = k
            break
    # If not specified, a UUID is used as the PK
    if not primary:
        table_data['attributes']['uuid'] = \
            dict(type='string', length=36, primary=True, required=True)
        primary = 'uuid'
    table_data['primary'] = primary
    return primary


def set_type(kwargs, col_desc):
    if col_desc['type'] == 'string':
        pass
    elif col_desc['type'] == 'integer':
        kwargs["type"] = int
    elif col_desc['type'] == 'boolean':
        kwargs["type"] = bool
    elif col_desc['type'] == 'enum':
        kwargs["type"] = click.Choice(col_desc['values'])
    else:
        raise Exception('Unknown column type %s' % col_desc['type'])


def proc_model(cli, package_name="unknown",
               hostenv="unknown",
               portenv="unknown",
               hostdefault="unknown",
               portdefault=0):
    # print("loading model")
    model = load_model(package_name)
    for table_name, table_data in model.iteritems():
        get_primary_key(table_data)
    for table_name, table_data in model.iteritems():
        try:
            attrs = {}
            for col_name, col_desc in table_data['attributes'].iteritems():
                try:
                    # Step 1: deal with object xrefs
                    if col_desc['type'] in model:
                        # If referencing another object, get the type of its primary key
                        tgt_name = col_desc['type']
                        tgt_data = model[tgt_name]
                        primary_col = tgt_data['primary']
                        table_data["attributes"][col_name]['type'] = tgt_data["attributes"][primary_col]["type"]
                    # Step 2: convert our special types to ones a CLI likes
                    if col_desc['type'] == 'uuid':
                        # UUIDs, from a CLI perspective,  are a form of
                        # string
                        table_data["attributes"][col_name]['type'] = 'string'
                        table_data["attributes"][col_name]['length'] = 64
                    if col_desc.get('primary', False):
                        attrs['_primary_key'] = col_name
                except:
                    print('During processing of attribute ', col_name)
                    raise
            if not '_primary_key' in attrs:
                raise Exception("One and only one primary key has to "
                                "be given to each column")
            attrs['__tablename__'] = table_data['api']['name']
            attrs['__objname__'] = table_data['api']['name'][:-1]  # chop off training 's'
            #
            # Create CDUD commands for the table
            #
            hosthelp = "Host of endpoint (%s) " % hostenv
            porthelp = "Port of endpoint (%s) " % portenv
            list = make_list_func(attrs['__tablename__'])
            list.func_name = "%s-list" % (attrs['__objname__'])
            list = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(list)
            list = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(list)
            cli.command()(list)

            show = make_show_func(attrs['__tablename__'], attrs['_primary_key'])
            show.func_name = "%s-show" % (attrs['__objname__'])
            show = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(show)
            show = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(show)
            show = click.argument(attrs['_primary_key'])(show)
            cli.command()(show)

            create = make_create_func(attrs['__tablename__'])
            create.func_name = "%s-create" % (attrs['__objname__'])
            create = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(create)
            create = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(create)
            for col_name, col_desc in table_data['attributes'].iteritems():
                kwargs = {}
                option_name = "--" + col_name
                kwargs["default"] = None
                required = col_desc.get('required', False)
                kwargs["help"] = col_desc.get('description', "no description")
                if required:
                    kwargs["required"] = True
                set_type(kwargs, col_desc)
                create = click.option(option_name, **kwargs)(create)
            cli.command()(create)

            update = make_update_func(attrs['__tablename__'], attrs['_primary_key'])
            update.func_name = "%s-update" % (attrs['__objname__'])
            update = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(update)
            update = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(update)
            for col_name, col_desc in table_data['attributes'].iteritems():
                if col_name == attrs['_primary_key']:
                    continue
                kwargs = {}
                option_name = "--" + col_name
                kwargs["default"] = None
                kwargs["help"] = col_desc.get('description', "no description")
                set_type(kwargs, col_desc)
                update = click.option(option_name, **kwargs)(update)
            update = click.argument(attrs['_primary_key'])(update)
            cli.command()(update)

            delete = make_delete_func(attrs['__tablename__'], attrs['_primary_key'])
            delete.func_name = "%s-delete" % (attrs['__objname__'])
            delete = click.option("--host", envvar=hostenv, default=hostdefault, help=hosthelp)(delete)
            delete = click.option("--port", envvar=portenv, default=portdefault, help=porthelp)(delete)
            delete = click.argument(attrs['_primary_key'])(delete)
            cli.command()(delete)

        except:
            print('During processing of table ', table_name)
            raise
