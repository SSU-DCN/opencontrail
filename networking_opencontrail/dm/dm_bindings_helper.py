# Copyright (c) 2019 OpenStack Foundation
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
#
import json

from oslo_config import cfg
from oslo_log import log as logging

from networking_opencontrail.dm.dm_topology import DmTopologyApi
from networking_opencontrail.dm.dm_topology import DmTopologyFile

LOG = logging.getLogger(__name__)

DM_MANAGED_VNIC_TYPE = 'baremetal'


class DmBindingsHelper(object):
    """DmBindingsHelper helps creating bindings for integration with FM.

    This check if host should be managed by Device Manager and
    prepare bindings for VMI with details about baremetal physical connections.
    """

    def __init__(self, tf_client):
        self.tf_client = tf_client
        topology_file = cfg.CONF.DM_INTEGRATION.topology
        if topology_file:
            self.topology = DmTopologyFile(self.tf_client)
        else:
            self.topology = DmTopologyApi(self.tf_client)

    def initialize(self):
        self.topology.initialize()

    def check_host_managed(self, host_id):
        return host_id in self.topology

    def get_bindings_for_host(self, host_id):
        node = self.topology.get_node(host_id)

        port_profiles = []
        for port in node['ports']:
            fabric_name = self.tf_client.read_fabric_name_from_switch(
                port['switch_name'])

            if not fabric_name:
                LOG.error("Cannot find fabric name for switch %s" %
                          port['switch_name'])
                raise FabricNotFoundError

            port_profiles.append({'port_id': port['port_name'],
                                  'switch_info': port['switch_name'],
                                  'fabric': fabric_name})

        profile = {'local_link_information': port_profiles}
        bindings_list = [('profile', json.dumps(profile)),
                         ('vnic_type', DM_MANAGED_VNIC_TYPE)]

        vpg = self._find_existing_vpg(node['ports'])
        if vpg:
            bindings_list.append(('vpg', vpg))

        return self.tf_client.make_key_value_pairs(bindings_list)

    def _find_existing_vpg(self, ports):
        pi = self.tf_client.read_pi_from_switch(ports[0]['switch_name'],
                                                ports[0]['port_name'])

        if not pi:
            LOG.error("PI %s on switch %s not found in API" %
                      (ports[0]['port_name'], ports[0]['switch_name']))
            raise PhysicalInterfaceNotFoundError

        vpg_refs = pi.get_virtual_port_group_back_refs() or []
        for vpg_ref in vpg_refs:
            vpg = self.tf_client.get_virtual_port_group(
                uuid=vpg_ref['uuid'])
            if vpg.get_virtual_port_group_user_created():
                continue
            pi_refs = vpg.get_physical_interface_refs() or []
            if self._check_refs_to_all_ports(pi_refs, ports):
                return vpg.fq_name[-1]
        return None

    def _check_refs_to_all_ports(self, pi_refs, ports):
        required_pi = {(port['switch_name'], port['port_name'])
                       for port in ports}
        existing_refs = {(ref['to'][-2], ref['to'][-1]) for ref in pi_refs}
        return required_pi == existing_refs


class FabricNotFoundError(Exception):
    pass


class PhysicalInterfaceNotFoundError(Exception):
    pass
