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
import uuid

from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_log import log as logging

from networking_opencontrail.drivers.vnc_api_driver import VncApiClient
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
        self.tf_client = VncApiClient()
        self.topology_loader = DmTopologyLoader()

    def initialize(self):
        self.topology = {}
        if self.enabled:
            self.topology = self.topology_loader.load()

    def create_vlan_tagging_for_port(self, context, port):
        node = self._get_node_for_port(port['port'])
        device_id = port['port'].get('device_id', '')
        if not node or not device_id:
            host_id = port['port'].get('binding:host_id', '')
            LOG.debug("Compute '%s' is not managed by Device Manager or no "
                      "connected VM. Binding for DM skipped. " % (host_id))
            return

        network_id = port['port']['network_id']
        vlan_tag = self._get_vlan_tag(context, network_id)
        if not vlan_tag:
            LOG.debug("No VLAN tag for port, binding for DM skipped.")
            return

        tf_project = self.tf_client.get_project(
            str(uuid.UUID(port['port']['tenant_id'])))
        vmi_name = self._make_vmi_name(port['port'])
        existing_vmi = self.tf_client.get_virtual_machine_interface(
            fq_name=tf_project.fq_name + [vmi_name])

        if existing_vmi:
            LOG.debug("VMI with bindings for DM exists, creating skipped.")
            return

        tf_vn = self.tf_client.get_virtual_network(network_id)
        if not tf_vn:
            LOG.error("Virtual Network '%s' not exists in TF." % network_id)
            return

        properties = self.tf_client.make_vmi_properties_with_vlan_tag(vlan_tag)
        bindings = self._get_bindings(port, node)
        vmi = self.tf_client.make_virtual_machine_interface(
            vmi_name, tf_vn, properties, bindings, tf_project)

        self.tf_client.create_virtual_machine_interface(vmi)
        LOG.debug("Created VMI with bindings for DM for port %s",
                  port['port']['id'])

    def delete_vlan_tagging_for_port(self, port):
        node = self._get_node_for_port(port)
        device_id = port.get('device_id', '')
        if not node or not device_id:
            return

        tf_project = self.tf_client.get_project(
            str(uuid.UUID(port['tenant_id'])))
        vmi_name = self._make_vmi_name(port)
        vmi_fq_name = tf_project.fq_name + [vmi_name]
        existing_vmi = self.tf_client.get_virtual_machine_interface(
            fq_name=vmi_fq_name)

        if existing_vmi:
            self._detach_vmi_from_vpg(existing_vmi)
            self.tf_client.delete_virtual_machine_interface(
                fq_name=vmi_fq_name)
            LOG.debug("Deleted VMI with bindings for DM for port %s" %
                      port['id'])

    def _detach_vmi_from_vpg(self, vmi):
        vpg_refs = vmi.get_virtual_port_group_back_refs()
        if not vpg_refs:
            return
        vpg = self.tf_client.get_virtual_port_group(vpg_refs[0]['uuid'])
        vpg.del_virtual_machine_interface(vmi)
        self.tf_client.update_virtual_port_group(vpg)

    def _get_node_for_port(self, port):
        if 'binding:host_id' not in port:
            return None
        host_id = port['binding:host_id']
        nodes = [n for n in self.topology['nodes'] if n['name'] == host_id]
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) > 1:
            LOG.error("For host '%s' there is more than one matched nodes." %
                      host_id)
        return None

    def _get_vlan_tag(self, context, network_id):
        network = self._core_plugin.get_network(context, network_id)
        vlan_tag = network.get('provider:segmentation_id', 0)
        network_type = network.get('provider:network_type', '')

        if network_type == 'vlan' and (0 < vlan_tag < 4095):
            return vlan_tag
        return None

    def _get_bindings(self, port, node):
        node_port = node['ports'][0]
        fabric_name = self.tf_client.read_fabric_name_from_switch(
            node_port['switch_name'])

        if not fabric_name:
            LOG.error("Cannot find fabric name for switch %s" %
                      node_port['switch_name'])
            raise FabricNotFoundError

        profile = {'local_link_information': [{
            'port_id': node_port['port_name'],
            'switch_id': node_port['switch_id'],
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

    @staticmethod
    def _make_vmi_name(port):
        network_id = port['network_id']
        device_id = port['device_id']
        vmi_name = "_vlan_tag_for_vm_%s_vn_%s" % (device_id, network_id)
        return vmi_name

    @property
    def enabled(self):
        return cfg.CONF.DM_INTEGRATION.enabled

    @property
    def _core_plugin(self):
        return directory.get_plugin()


class FabricNotFoundError(Exception):
    pass
