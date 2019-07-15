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

from neutron_lib.plugins import directory
from oslo_log import log as logging

from networking_opencontrail.drivers.rest_driver import ContrailRestApiDriver
from networking_opencontrail.ml2.dm_topology_loader import DmTopologyLoader

LOG = logging.getLogger(__name__)

DM_MANAGED_VNIC_TYPE = 'baremetal'


class DeviceManagerIntegrator(object):
    """Device Manager Integrator for Tungsten Fabric networking.

    This class provides support for Device Manager to inform it
    about L2 virtual networks that are used by virtual machines.
    It allows DM to properly configure physical devices inside Fabric.
    """

    def __init__(self):
        self.tf_rest_driver = ContrailRestApiDriver()
        self.topology_loader = DmTopologyLoader()

    def initialize(self):
        self.topology = self.topology_loader.load()

    def enable_vlan_tag_on_port(self, context, port):
        network_id = port['port']['network_id']
        network = self._core_plugin.get_network(context, network_id)
        vlan_tag = network['provider:segmentation_id']
        vlan_tag_dict = {'sub_interface_vlan_tag': vlan_tag}

        port['port']['virtual_machine_interface_properties'] = vlan_tag_dict
        port['port']['binding:vnic_type'] = DM_MANAGED_VNIC_TYPE

    def add_port_binding_to_port(self, port):
        bindings = self._get_bindings(port)
        port['port'].update(bindings)

    def _get_bindings(self, port):
        if 'binding:host_id' not in port['port']:
            return {}
        host_id = port['port']['binding:host_id']
        nodes = [n for n in self.topology['nodes'] if n['name'] == host_id]
        if len(nodes) == 1:
            node_port = nodes[0]['ports'][0]
            profile = {
                'port_id': node_port['port_name'],
                'switch_id': node_port['switch_id'],
                'switch_info': node_port['switch_name'],
                'fabric': node_port['fabric'],
            }
            binding = {
                'binding:profile': {'local_link_information': [profile]},
                'binding:vnic_type': DM_MANAGED_VNIC_TYPE
            }

            vpg = self._find_existing_vpg(node_port['switch_name'],
                                          node_port['port_name'])
            if vpg:
                binding.update({'binding:vpg': vpg})

            return binding
        else:
            LOG.info("Compute '%s' is not managed by Device Manager. "
                     "Binding for DM skipped. " % (host_id))
            return {}

    def _find_existing_vpg(self, switch_node, port_node):
        request_query = {
            'parent_fq_name_str': '%s:%s' % (
                "default-global-system-config", switch_node)}
        physical_interfaces = \
            self.tf_rest_driver.list_resource('physical-interface',
                                              request_query)[1]
        pi = [pi for pi in physical_interfaces['physical-interfaces']
              if pi['fq_name'][-1] == port_node]

        if len(pi) == 1:
            pi_uuid = pi[0]['uuid']
            pi_details = self.tf_rest_driver.get_resource('physical-interface',
                                                          None,
                                                          pi_uuid)[1]
            # TODO(kamman): select first auto-generated VPG
            if 'virtual_port_group_back_refs' in pi_details[
                'physical-interface']:
                return pi_details['physical-interface'][
                    'virtual_port_group_back_refs'][0]['to'][-1]
        return None

    @property
    def enabled(self):
        return not self.topology == {}

    @property
    def _core_plugin(self):
        return directory.get_plugin()
