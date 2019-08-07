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

from oslo_log import log as logging

from networking_opencontrail.dm.dm_topology_loader import DmTopologyLoader

LOG = logging.getLogger(__name__)

DM_MANAGED_VNIC_TYPE = 'baremetal'


class DmNodeHelper(object):
    def __init__(self, tf_client):
        self.tf_client = tf_client
        self.topology_loader = DmTopologyLoader()

    def initialize(self):
        self.topology = self.topology_loader.load()

    def check_node_managed(self, host_id):
        node = self._get_node_from_file(host_id)
        return node is not None

    def get_bindings_for_node(self, host_id):
        node = self._get_node_from_file(host_id)
        if not node:
            LOG.error("Try to get binding for node %s, but node not found" %
                      host_id)
            raise NodeNotFoundError

        node_port = node['ports'][0]
        fabric_name = self.tf_client.read_fabric_name_from_switch(
            node_port['switch_name'])

        if not fabric_name:
            LOG.error("Cannot find fabric name for switch %s" %
                      node_port['switch_name'])
            raise FabricNotFoundError

        profile = {'local_link_information': [{
            'port_id': node_port['port_name'],
            'switch_info': node_port['switch_name'],
            'fabric': fabric_name
        }]}
        bindings_list = [('profile', json.dumps(profile)),
                         ('vnic_type', DM_MANAGED_VNIC_TYPE)]

        vpg = self._find_existing_vpg(node_port['switch_name'],
                                      node_port['port_name'])
        if vpg:
            bindings_list.append(('vpg', vpg))

        return self.tf_client.make_key_value_pairs(bindings_list)

    def _get_node_from_file(self, host_id):
        nodes = [n for n in self.topology['nodes'] if n['name'] == host_id]
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) > 1:
            LOG.error("For host '%s' there is more than one matched nodes." %
                      host_id)
        return None

    def _find_existing_vpg(self, switch_node, port_node):
        pi = self.tf_client.read_pi_from_switch(switch_node, port_node)
        if pi:
            vpg_refs = pi.get_virtual_port_group_back_refs() or []
            for vpg_ref in vpg_refs:
                vpg = self.tf_client.get_virtual_port_group(
                    uuid=vpg_ref['uuid'])
                if not vpg.get_virtual_port_group_user_created():
                    return vpg.fq_name[-1]
        return None


class FabricNotFoundError(Exception):
    pass


class NodeNotFoundError(Exception):
    pass
