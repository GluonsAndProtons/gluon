# Copyright (c) 2015 Cisco Systems, Inc.
# All Rights Reserved
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

from neutronclient.v2_0 import client as clientv20
from gluon.backends import base
import gluon.backends.neutron_model as neutron_model
from oslo_config import cfg


API_SERVICE_OPTS = [
    cfg.StrOpt('ovs_bridge',
               default='br-int',
               help='The OVS bridge that Neutron uses - this is not in the binding info it returns'),
    cfg.StrOpt('username',
               help='Neutron username when binding'),
    cfg.StrOpt('password',
               help='Neutron password when binding'),
    cfg.StrOpt('tenant',
               help='Neutron tenant when binding'),
    cfg.StrOpt('auth_url',
               help='Location to get Neutron auth'),
]

CONF = cfg.CONF
opt_group = cfg.OptGroup(name='gluon',
                         title='Options for the gluon-api service')
CONF.register_group(opt_group)
CONF.register_opts(API_SERVICE_OPTS, opt_group)


class Provider(base.Provider):

    def __init__(self, logger):
        self._drivers = {}
        self._logger = logger

    def driver_for(self, backend):
        if backend['service_type'] == 'neutron':
            return Driver(backend, self._logger)
        else:
            return None


class Driver(base.Driver):

    def __init__(self, backend, logger):
        self._logger = logger

        self._client = clientv20.Client(username=CONF.neutron.username,
                                        password=CONF.neutron.password,
                                        tenant_name=CONF.neutron.tenant,
                                        auth_url=CONF.neutron.auth_url)
        if not self._client:
            raise ValueError('Bad Neutron credentials')

    def bind(self, port_id, device_owner, zone, device_id, host_id,
             binding_profile):
        # TODO zone is presently not sent to neutron, probably bad...
        self._logger.debug('binding port %s' % port_id)
        port_req_body = {'port': {
            'device_id': device_id,
            'device_owner': device_owner,
            'binding:host_id': host_id,
            'binding:profile': binding_profile}}
        rv = self._client.update_port(port_id, port_req_body)
        self._logger.debug('Return from update-port is %s ' % rv)

        return True

    def unbind(self, port_id):
        self._logger.debug('unbinding port %s' % port_id)
        port_req_body = {
            'port': {'device_id': '', 'device_owner': '',
                     'binding:host_id': None}}
        rv = self._client.update_port(port_id, port_req_body)
        pass

    def port(self, port_id):
        # First, fetch the port from Neutron in Neutron's own format
        client = self._client
        rv = client.show_port(port_id)
        neutron_port = rv['port']
        self._logger.debug(neutron_port)

        self._logger.error('Fetching port data for %s' % port_id)

        # Then convert to a Gluon object.

        gluon_port = {}

        # TODO should we just be transmitting the binding details and adding
        # to it or copying it over
        # robustly as we do with the port itself?
        for f in ['id', 'device_owner', 'device_id',
                  'binding:vif_type', 'binding:vnic_type',
                  'binding:profile', 'binding:vif_details', 'mac_address',
                  'network_id']:
            gluon_port[f] = neutron_port.get(f)

        if neutron_port.get('device_owner'):
            gluon_port['bound'] = True
        else:
            gluon_port['bound'] = False

        gluon_port['host'] = neutron_port.get('binding:host_id')

        # TODO at the moment, Openstack knows, uses and returns a network name.
        # We keep this as a label.
        gluon_port['label'] = "ID:%s" % neutron_port.get('network_id', '')
        # neutron_network['name']

        # Probably should just go away - don't want Nova bothering about
        # tenancy
        gluon_port['tenant_id'] = neutron_port.get('network_id', '')

        vif_type = neutron_port.get('binding:vif_type')
        port_details = neutron_port.get('binding:vif_details')

        # Not used for all binding types, but Neutron always sets it
        # in Nova's datastructure.  In some cases it's not really Neutron's
        # problem...
        devname = "tap" + gluon_port['id']
        devname = devname[:neutron_model.NIC_NAME_LEN]
        gluon_port['devname'] = devname

        bridge = None
        ovs_interfaceid = None
        should_create_bridge = False
        if vif_type == neutron_model.VIF_TYPE_OVS:
            bridge = CONF.neutron.ovs_bridge
            ovs_interfaceid = neutron_port['id']
        elif vif_type == neutron_model.VIF_TYPE_BRIDGE:
            bridge = "brq" + neutron_port['network_id']
            should_create_bridge = True
        elif vif_type == neutron_model.VIF_TYPE_DVS:
            # The name of the DVS port group will contain the neutron
            # network id
            bridge = neutron_port['network_id']
        elif (vif_type == neutron_model.VIF_TYPE_VHOSTUSER and
              port_details.get(neutron_model.VIF_DETAILS_VHOSTUSER_OVS_PLUG,
                               False)):
            bridge = CONF_neutron_ovs_bridge
            ovs_interfaceid = neutron_port['id']

        # TODO think this wants to die - it was intended to be binding_details
        # and clearly it works without
        if 'binding:details' not in gluon_port:
            gluon_port['binding:details'] = {}

        if bridge is not None:
            # This is the bridge or switch to which we should attach,
            # if that's the kind of binding we're using.
            gluon_port['binding:details']['bridge'] = bridge
        if ovs_interfaceid is not None:
            # And if it's a switch then we mark the port with a magic
            # number that the backend recognises.
            gluon_port['binding:details']['ovs_interface_id'] = \
                ovs_interfaceid
        if should_create_bridge is not None:
            # If it's just a bridge, then either the compute or
            # network service could be responsible for creating it.
            # The network service should tell the compute service if
            # it needs to.
            gluon_port['binding:details']['should_create_bridge'] = \
                should_create_bridge

        vif_active = False
        if (neutron_port['admin_state_up'] is False or
                neutron_port['status'] == 'ACTIVE'):
            vif_active = True
        gluon_port['vif_active'] = vif_active

        return gluon_port
