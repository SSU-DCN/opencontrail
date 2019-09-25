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

from neutron_lib import constants
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

    REQUIRED_PORT_FIELDS = [
        'binding:host_id',
        'device_id',
        'device_owner',
        'network_id']

    def __init__(self):
        self.tf_client = VncApiClient()
        self.bindings_helper = DmBindingsHelper(self.tf_client)

    def initialize(self):
        if self.enabled:
            self.bindings_helper.initialize()

    def sync_vlan_tagging_for_port(self, context, port, previous_port):
        if self._check_data_was_changed(port, previous_port):
            self.delete_vlan_tagging_for_port(context, previous_port)

        if not self._check_should_be_tagged(port):
            host_id = port.get('binding:host_id')
            LOG.debug("Compute '%s' is not managed by Device Manager or no "
                      "connected VM. DM integration skipped. " % (host_id))
            return

        network_id = port['network_id']
        vlan_tag = self._get_vlan_tag(context, network_id)
        if not vlan_tag:
            LOG.debug("No VLAN tag for port, binding for DM skipped.")
            return

        tf_project = self.tf_client.get_project(
            str(uuid.UUID(port['tenant_id'])))
        vmi_name = self._make_vmi_name(port)
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
            port['binding:host_id'])
        vmi = self.tf_client.make_virtual_machine_interface(
            vmi_name, tf_vn, properties, bindings, tf_project)

        self.tf_client.create_virtual_machine_interface(vmi)
        LOG.debug("Created VMI with bindings for DM for port %s", port['id'])

    def delete_vlan_tagging_for_port(self, context, port):
        if not self._check_contains_required_fields(port):
            LOG.debug("Port %s cannot be VLAN-tagged. Trying to delete VMI for"
                      "DM skipped" % port['id'])
            return

        tf_project = self.tf_client.get_project(
            str(uuid.UUID(port['tenant_id'])))
        vmi_name = self._make_vmi_name(port)
        vmi_fq_name = tf_project.fq_name + [vmi_name]
        existing_vmi = self.tf_client.get_virtual_machine_interface(
            fq_name=vmi_fq_name)

        vmi_ports = self._core_plugin.get_ports(
            context, filters={
                'network_id': [port['network_id']],
                'binding:host_id': [port['binding:host_id']]})
        are_ports_assigned = any(
            port for port in vmi_ports if self._check_should_be_tagged(port))
        if existing_vmi and not are_ports_assigned:
            self._detach_vmi_from_vpg(existing_vmi)
            self.tf_client.delete_virtual_machine_interface(
                fq_name=vmi_fq_name)
            LOG.debug("Deleted VMI with bindings for DM for port %s" %
                      port['id'])

    def _check_data_was_changed(self, current, previous):
        for field in self.REQUIRED_PORT_FIELDS:
            if current.get(field) != previous.get(field):
                return True
        return False

    def _check_contains_required_fields(self, port):
        for field in self.REQUIRED_PORT_FIELDS:
            if field not in port:
                return False
        return True

    def _check_should_be_tagged(self, port):
        if not self._check_contains_required_fields(port):
            return False

        host_id = port.get('binding:host_id')
        device_id = port.get('device_id', None)
        compute_owner = port.get('device_owner', '').startswith(
            constants.DEVICE_OWNER_COMPUTE_PREFIX)
        managed_host = self.bindings_helper.check_host_managed(host_id)
        if not managed_host or not device_id or not compute_owner:
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

        if network_type == constants.TYPE_VLAN and (
            constants.MIN_VLAN_TAG <= vlan_tag <= constants.MAX_VLAN_TAG):
            return vlan_tag
        return None

    @staticmethod
    def _make_vmi_name(port):
        network_id = port['network_id']
        device_id = port['binding:host_id']
        vmi_name = "_vlan_tag_for_vn_{}_compute_{}".format(
            network_id, device_id)
        return vmi_name

    @property
    def enabled(self):
        return cfg.CONF.DM_INTEGRATION.enabled

    @property
    def _core_plugin(self):
        return directory.get_plugin()


class FabricNotFoundError(Exception):
    pass
