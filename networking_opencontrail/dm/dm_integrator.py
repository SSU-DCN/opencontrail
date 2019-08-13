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

import uuid

from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_log import log as logging

from networking_opencontrail.dm.dm_bindings_helper import DmBindingsHelper
from networking_opencontrail.drivers.vnc_api_driver import VncApiClient

LOG = logging.getLogger(__name__)


class DeviceManagerIntegrator(object):
    """Device Manager Integrator for Tungsten Fabric networking.

    This class provides support for Device Manager to inform it
    about L2 virtual networks that are used by virtual machines.
    It allows DM to properly configure physical devices inside Fabric.
    """

    def __init__(self):
        self.tf_client = VncApiClient()
        self.bindings_helper = DmBindingsHelper(self.tf_client)

    def initialize(self):
        if self.enabled:
            self.bindings_helper.initialize()

    def create_vlan_tagging_for_port(self, context, port):
        if not self._check_should_be_tagged(port['port']):
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
        bindings = self.bindings_helper.get_bindings_for_host(
            port['port']['binding:host_id'])
        vmi = self.tf_client.make_virtual_machine_interface(
            vmi_name, tf_vn, properties, bindings, tf_project)

        self.tf_client.create_virtual_machine_interface(vmi)
        LOG.debug("Created VMI with bindings for DM for port %s",
                  port['port']['id'])

    def delete_vlan_tagging_for_port(self, port):
        if not self._check_should_be_tagged(port):
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

    def _check_should_be_tagged(self, port):
        host_id = port.get('binding:host_id')
        device_id = port.get('device_id', None)
        compute_owner = port.get('device_owner', '').startswith('compute:')
        managed_host = self.bindings_helper.check_host_managed(host_id)
        if not managed_host or not device_id or not compute_owner:
            LOG.debug("Compute '%s' is not managed by Device Manager or no "
                      "connected VM. DM integration skipped. " % (host_id))
            return False
        return True

    def _detach_vmi_from_vpg(self, vmi):
        vpg_refs = vmi.get_virtual_port_group_back_refs()
        if not vpg_refs:
            return
        vpg = self.tf_client.get_virtual_port_group(vpg_refs[0]['uuid'])
        vpg.del_virtual_machine_interface(vmi)
        self.tf_client.update_virtual_port_group(vpg)

    def _get_vlan_tag(self, context, network_id):
        network = self._core_plugin.get_network(context, network_id)
        vlan_tag = network.get('provider:segmentation_id', 0)
        network_type = network.get('provider:network_type', '')

        if network_type == 'vlan' and (0 < vlan_tag < 4095):
            return vlan_tag
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
