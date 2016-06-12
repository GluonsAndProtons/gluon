#    Copyright 2016, Ericsson AB
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from gluon.common import exception
from oslo_log import log as logging
from gluon.core.manager import ApiManager
from oslo_config import cfg


from gluon.backends import base as BackendBase
# This has to be dne to get the Database Models
# build before the API is build.
# It should be done in a better way.
from gluon.db.sqlalchemy import models

LOG = logging.getLogger(__name__)
logger = LOG


class GluonManager(ApiManager):
    def __init__(self):
        self.backend_manager = BackendBase.Manager(cfg.CONF)
        self.gluon_objects = {}
        super(GluonManager, self).__init__()


    def get_all_ports(self, api_class, obj_class):
        backend_class = self.get_gluon_object('GluonServiceBackend')
        backend_list = backend_class.list()
        port_list = []
        for backend in backend_list:
            port_list.extend(self._do_backend_get_all_ports(backend))
        return port_list

    def _do_backend_get_all_ports(self, backend):
        """Get all ports for a specific backend
        """
        driver = self.backend_manager.get_backend_driver(backend)
        return driver.ports()

    def get_one_ports(self, api_class, obj_class, key):
        port = obj_class.get_by_primary_key(key)
        backend_class = self.get_gluon_object('GluonServiceBackend')
        backend = backend_class.get_by_primary_key(port.owner)
        return self._do_backend_get_one_port(backend, key)

    def _do_backend_get_one_port(self, backend, port_id):
        """Get on port from a specific backend
        """
        driver = self.backend_manager.get_backend_driver(backend)
        return driver.port(port_id)

    def create_ports(self, api_class, port):
        owner = port.owner
        LOG.debug('Creating a new port for backend %s' % owner)
        backend_class = self.get_gluon_object('GluonServiceBackend')
        backend = backend_class.get_by_name(owner)
        if not backend:
            raise exception.BackendDoesNotExsist(name=owner)
        port.create()
        return api_class.build(port)
    #
    # /ports/<key>/update
    #
    def update_ports(self, api_class, obj_class, key, new_values):
        return api_class.build(obj_class.update(key, new_values))

    def delete_ports(self, api_class, obj_class, key):
        return obj_class.delete(key)

    def get_all_backends(self, api_class, obj_class):
        return obj_class.as_list(obj_class.list())

    def get_one_backends(self, api_class, obj_class, key):
        return obj_class.get_by_primary_key(key).as_dict()

    def create_backends(self, api_class, backend):
        backend.create()
        return api_class.build(backend)
    #
    # /backends/<key>/update
    #
    def update_backends(self, api_class, obj_class, key, new_values):
        return api_class.build(obj_class.update(key, new_values))

    def delete_backends(self, api_class, obj_class, key):
        return obj_class.delete(key)

    def _get_backend_of_port(self, port):
        backend_class = self.get_gluon_object('GluonServiceBackend')
        backend = backend_class.get_by_primary_key(port.owner)
        return backend

    #
    # /ports/<key>/bind
    #
    def bind_ports(self, api_class, obj_class, uuid, args):
        binding_profile = {
            'pci_profile': args.get('pci_profile', ''),
            'rxtx_factor': args.get('rxtx_factor','')
            # TODO add negotiation here on binding types that are valid
            # (requires work in Nova)
        }
        port = obj_class.get_by_primary_key(uuid)
        backend = self._get_backend_of_port(port)
        self._do_backend_bind(backend, uuid,
                                     args['device_owner'], args.get('zone',''),
                                     args['device_id'], args['host_id'],
                                     binding_profile)
        new_values = { 'device_owner': args['device_owner'], 'device_id': args['device_id']}
        return api_class.build(obj_class.update(uuid, new_values))

    def _do_backend_bind(self, backend, port_id, device_owner, zone, device_id,
                         host, binding_profile):
        """Helper function to get a port bound by the backend.

        Once bound, the port is owned by the network service and cannot be
        rebound by that service or any other without unbinding first.

        Binding consists of the compute and network services agreeing a
        drop point; the compute service has previously set binding
        requirements on the port, and at this point says where the port
        must be bound (the host); the network service will work out what
        it can achieve and set information on the port indicating the drop
        point it has chosen.

        Typically there is some prior knowledge on both sides of what
        binding types will be acceptable, so this process could be
        improved.
        """

        logger.debug('Binding port %s on backend %s: compute: %s/%s/%s location %s'
                     % (port_id, backend['name'], device_owner,
                        zone, device_id, host))
        driver = self.backend_manager.get_backend_driver(backend)
        # TODO these are not thoroughly documented or validated and are a
        # part of the API.  Write down what the values must be, must mean
        # and how the backend can use them.
        return driver.bind(port_id,
                           device_owner, zone, device_id,
                           host, binding_profile)

        # TODO required?  Do we trust the backend to set this?
        # ports[port_id]['zone'] = zone

    #
    # /ports/<key>/unbind
    #
    def unbind_ports(self, api_class, obj_class, uuid, args):
        port = obj_class.get_by_primary_key(uuid)
        backend = self._get_backend_of_port(port)
        # Not very distributed-fault-tolerant, but no retries yet
        self._do_backend_unbind(backend, uuid)
        new_values = {'device_owner': '', 'device_id': ''}
        return api_class.build(obj_class.update(uuid, new_values))

    def _do_backend_unbind(self, backend, port_id):
        """Helper function to get a port unbound from the backend.

        Once unbound, the port becomes ownerless and can be bound by
        another service.  When unbound, the compute and network services
        have mutually agreed to stop exchanging packets at their drop
        point.

        """
        driver = self.backend_manager.get_backend_driver(backend)
        return driver.unbind(port_id)


