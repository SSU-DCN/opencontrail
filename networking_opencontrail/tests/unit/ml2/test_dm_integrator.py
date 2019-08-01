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

import ddt
import mock

from networking_opencontrail.drivers.vnc_api_driver import VncApiClient
from networking_opencontrail.ml2 import dm_integrator
from networking_opencontrail.ml2.dm_topology_loader import ConfigInvalidFormat
from networking_opencontrail.tests import base


@ddt.ddt
class DeviceManagerIntegratorTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF",
                APISERVER=mock.MagicMock(topology=None))
    def setUp(self, config):
        super(DeviceManagerIntegratorTestCase, self).setUp()
        dm_integrator.directory.get_plugin = mock.Mock()
        dm_integrator.VncApiClient = mock.Mock(spec_set=VncApiClient)

        self.dm_integrator = dm_integrator.DeviceManagerIntegrator()
        self.dm_integrator.topology_loader.load = mock.Mock(
            return_value=self._get_topology())
        self.dm_integrator.initialize()

        self.core_plugin = self.dm_integrator._core_plugin
        self.tf_client = self.dm_integrator.tf_client

    def tearDown(self):
        super(DeviceManagerIntegratorTestCase, self).tearDown()

    @mock.patch("oslo_config.cfg.CONF")
    def test_topology_should_be_validated_on_initializing(self, _):
        self.dm_integrator.topology_loader.load = \
            mock.Mock(side_effect=ConfigInvalidFormat)
        self.assertRaises(ConfigInvalidFormat, self.dm_integrator.initialize)

    @ddt.data(1, 100, 4094)
    def test_create_tagging_for_port_first_in_vpg(self, vlan_tag):
        self._mock_core_get_network(segmentation_id=vlan_tag)
        self._mock_tf_client_when_no_vpg()
        self._mock_tf_client_get_vmi(None)
        tf_project = self._mock_tf_client_get_project()
        tf_vn = self._mock_tf_client_get_vn()
        tf_properties = self._mock_tf_client_make_vmi_properties()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()
        tf_created_vmi = self._mock_tf_client_make_vmi()
        context = self._get_fake_context()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_id': 'mac-address',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fab01'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=tf_project.fq_name + [expected_vmi_name]),
            mock.call.get_virtual_network("net-1"),
            mock.call.make_vmi_properties_with_vlan_tag(vlan_tag),
            mock.call.read_pi_from_switch("leaf1", "xe-0/0/1"),
            mock.call.make_key_value_pairs(expected_bindings),
            mock.call.make_virtual_machine_interface(
                expected_vmi_name, tf_vn, tf_properties,
                tf_kvpairs, tf_project),
            mock.call.create_virtual_machine_interface(tf_created_vmi)
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.core_plugin.get_network.assert_called_with(context, "net-1")

    def test_create_tagging_for_port_when_only_manual_vpg(self):
        """Don't connect to VPGs created manually by someone."""
        self._mock_core_get_network(segmentation_id=100)
        self._mock_tf_client_when_only_manual_created_vpg_exists()
        self._mock_tf_client_get_vmi(None)
        tf_project = self._mock_tf_client_get_project()
        tf_vn = self._mock_tf_client_get_vn()
        tf_properties = self._mock_tf_client_make_vmi_properties()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()
        tf_created_vmi = self._mock_tf_client_make_vmi()
        context = self._get_fake_context()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_id': 'mac-address',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fab01'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=tf_project.fq_name + [expected_vmi_name]),
            mock.call.get_virtual_network("net-1"),
            mock.call.make_vmi_properties_with_vlan_tag(100),
            mock.call.read_pi_from_switch("leaf1", "xe-0/0/1"),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.make_key_value_pairs(expected_bindings),
            mock.call.make_virtual_machine_interface(
                expected_vmi_name, tf_vn, tf_properties,
                tf_kvpairs, tf_project),
            mock.call.create_virtual_machine_interface(tf_created_vmi)
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.core_plugin.get_network.assert_called_with(context, "net-1")

    def test_create_tagging_for_port_when_autocreated_vpg_exists(self):
        self._mock_core_get_network()
        self._mock_tf_client_when_autocreated_vpg_exists()
        self._mock_tf_client_get_vmi(None)
        tf_project = self._mock_tf_client_get_project()
        tf_vn = self._mock_tf_client_get_vn()
        tf_properties = self._mock_tf_client_make_vmi_properties()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()
        tf_created_vmi = self._mock_tf_client_make_vmi()
        context = self._get_fake_context()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_id': 'mac-address',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fab01'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal'),
                             ('vpg', 'vpg-2')]
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=tf_project.fq_name + [expected_vmi_name]),
            mock.call.get_virtual_network("net-1"),
            mock.call.make_vmi_properties_with_vlan_tag(100),
            mock.call.read_pi_from_switch("leaf1", "xe-0/0/1"),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.get_virtual_port_group(uuid='vpg-id-2'),
            mock.call.make_key_value_pairs(expected_bindings),
            mock.call.make_virtual_machine_interface(
                expected_vmi_name, tf_vn, tf_properties,
                tf_kvpairs, tf_project),
            mock.call.create_virtual_machine_interface(tf_created_vmi)
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.core_plugin.get_network.assert_called_with(context, "net-1")

    @ddt.data({'binding:host_id': 'not-managed', 'device_id': 'vm-1'},
              {'device_id': 'vm-1'})
    def test_not_created_tagging_when_no_node(self, port_data):
        context = self._get_fake_context()

        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.tf_client.assert_not_called()
        self.core_plugin.assert_not_called()

    @ddt.data(None, 0, 4095)
    def test_not_created_tagging_when_invalid_vlan(self, invalid_tag):
        context = self._get_fake_context()
        self._mock_core_get_network(segmentation_id=invalid_tag)

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.core_plugin.get_network.assert_called_with(context, "net-1")
        self.tf_client.assert_not_called()

    def test_not_created_tagging_when_network_not_vlan(self):
        context = self._get_fake_context()
        self._mock_core_get_network(net_type='not-vlan')

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}

        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.core_plugin.get_network.assert_called_with(context, "net-1")
        self.tf_client.assert_not_called()

    def test_not_created_tagging_when_no_device_id(self):
        self._mock_core_get_network()
        context = self._get_fake_context()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.tf_client.create_virtual_machine_interface.assert_not_called()

    def test_not_created_tagging_when_vn_not_exists_in_tf(self):
        context = self._get_fake_context()
        self._mock_core_get_network()
        self._mock_tf_client_get_vmi(None)
        tf_project = self._mock_tf_client_get_project()
        self._mock_tf_client_get_vn(no_vn=True)

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        expected_vmi_name = '_vlan_tag_for_vm_vm-1_vn_net-1'
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=tf_project.fq_name + [expected_vmi_name]),
            mock.call.get_virtual_network("net-1")
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.tf_client.make_virtual_machine_interface.assert_not_called()
        self.tf_client.create_virtual_machine_interface.assert_not_called()
        self.core_plugin.get_network.assert_called_with(context, "net-1")

    def test_use_existing_vmi_on_create_tagging(self):
        self._mock_core_get_network()
        existing_vmi = mock.Mock()
        self._mock_tf_client_get_vmi(existing_vmi)
        tf_project = self._mock_tf_client_get_project()
        context = self._get_fake_context()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=tf_project.fq_name + [expected_vmi_name])]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.core_plugin.get_network.assert_called_with(context, "net-1")
        self.tf_client.create_virtual_machine_interface.assert_not_called()

    def test_delete_tagging(self):
        existing_vmi, vpg = self._mock_tf_client_vmi_with_vpg()
        tf_project = self._mock_tf_client_get_project()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.delete_vlan_tagging_for_port(port_data)

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        vmi_fq_name = tf_project.fq_name + [expected_vmi_name]
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=vmi_fq_name),
            mock.call.get_virtual_port_group("vpg-id-1"),
            mock.call.update_virtual_port_group(vpg),
            mock.call.delete_virtual_machine_interface(fq_name=vmi_fq_name)]
        self.tf_client.assert_has_calls(tf_expected_calls)
        vpg.del_virtual_machine_interface.assert_called_with(existing_vmi)

    def test_delete_tagging_when_no_vpg_refs(self):
        self._mock_tf_client_vmi_without_vpg()
        tf_project = self._mock_tf_client_get_project()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.delete_vlan_tagging_for_port(port_data)

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        vmi_fq_name = tf_project.fq_name + [expected_vmi_name]
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=vmi_fq_name),
            mock.call.delete_virtual_machine_interface(fq_name=vmi_fq_name)]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.tf_client.get_virtual_port_group.assert_not_called()

    @ddt.data({'binding:host_id': 'not-managed', 'device_id': 'vm-1'},
              {'device_id': 'vm-1'})
    def test_not_try_delete_tagging_when_no_node(self, port_data):
        self.dm_integrator.delete_vlan_tagging_for_port(port_data)
        self.tf_client.assert_not_called()

    def test_not_try_delete_tagging_when_no_vmi(self):
        self._mock_tf_client_get_vmi(None)
        tf_project = self._mock_tf_client_get_project()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.delete_vlan_tagging_for_port(port_data)

        expected_vmi_name = "_vlan_tag_for_vm_vm-1_vn_net-1"
        vmi_fq_name = tf_project.fq_name + [expected_vmi_name]
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=vmi_fq_name)]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.tf_client.delete_virtual_machine_interface.assert_not_called()

    def _get_topology(self):
        switch_port = {'name': 'ens1f1', 'switch_name': 'leaf1',
                       'port_name': 'xe-0/0/1', 'switch_id': 'mac-address',
                       'fabric': 'fab01'}
        return {'nodes': [{'name': 'compute1', 'ports': [switch_port]}]}

    def _get_fake_context(self, **kwargs):
        return mock.Mock(**kwargs)

    def _mock_tf_client_get_project(self):
        project = mock.Mock(fq_name=['project-1'])
        self.tf_client.get_project = mock.Mock(return_value=project)
        return project

    def _mock_tf_client_get_vn(self, no_vn=False):
        vn = None if no_vn else mock.Mock(id='vn-1')
        self.tf_client.get_virtual_network = mock.Mock(return_value=vn)
        return vn

    def _mock_tf_client_get_vmi(self, vmi=None):
        self.tf_client.get_virtual_machine_interface = mock.Mock(
            return_value=vmi)

    def _mock_tf_client_vmi_with_vpg(self):
        vpg = mock.Mock(fq_name=['parent-name', 'vpg-1'], uuid='vpg-id-1')
        vpg_refs = [{'to': vpg.fq_name, 'uuid': vpg.uuid}]
        self.tf_client.get_virtual_port_group = mock.Mock(return_value=vpg)

        vmi = mock.Mock()
        vmi.get_virtual_port_group_back_refs = mock.Mock(return_value=vpg_refs)
        self._mock_tf_client_get_vmi(vmi)

        return vmi, vpg

    def _mock_tf_client_vmi_without_vpg(self):
        vmi = mock.Mock()
        vmi.get_virtual_port_group_back_refs = mock.Mock(return_value=None)
        self._mock_tf_client_get_vmi(vmi)
        return vmi

    def _mock_tf_client_make_vmi_properties(self):
        properties = mock.Mock()
        self.tf_client.make_vmi_properties_with_vlan_tag = mock.Mock(
            return_value=properties)
        return properties

    def _mock_tf_client_make_vmi(self):
        vmi = mock.Mock()
        self.tf_client.make_virtual_machine_interface = mock.Mock(
            return_value=vmi)
        return vmi

    def _mock_tf_client_make_key_value_pairs(self):
        kv_pairs = mock.Mock()
        self.tf_client.make_key_value_pairs = mock.Mock(return_value=kv_pairs)
        return kv_pairs

    def _mock_tf_client_when_no_vpg(self):
        self._mock_tf_client_physical_interface(vpg_refs=None)

    def _mock_tf_client_when_only_manual_created_vpg_exists(self):
        """Mock existing one, manual-created VPG"""
        vpg_1 = mock.Mock(fq_name=['parent-name', 'vpg-1'], uuid='vpg-id-1')
        vpg_1.get_virtual_port_group_user_created = mock.Mock(
            return_value=True)
        self.tf_client.get_virtual_port_group = mock.Mock(side_effect=[vpg_1])

        vpg_refs = [{'to': vpg_1.fq_name, 'uuid': vpg_1.uuid}]
        self._mock_tf_client_physical_interface(vpg_refs)

    def _mock_tf_client_when_autocreated_vpg_exists(self):
        """Mock existing two VPGs: one manual created, one auto-generated"""
        vpg_1 = mock.Mock(fq_name=['parent-name', 'vpg-1'], uuid='vpg-id-1')
        vpg_1.get_virtual_port_group_user_created = mock.Mock(
            return_value=True)
        vpg_2 = mock.Mock(fq_name=['parent-name', 'vpg-2'], uuid='vpg-id-2')
        vpg_2.get_virtual_port_group_user_created = mock.Mock(
            return_value=False)
        self.tf_client.get_virtual_port_group = mock.Mock(
            side_effect=[vpg_1, vpg_2])

        vpg_refs = [{'to': vpg_1.fq_name, 'uuid': vpg_1.uuid},
                    {'to': vpg_2.fq_name, 'uuid': vpg_2.uuid}]
        self._mock_tf_client_physical_interface(vpg_refs)

    def _mock_tf_client_physical_interface(self, vpg_refs):
        physical_interface = mock.Mock()
        physical_interface.get_virtual_port_group_back_refs = mock.Mock(
            return_value=vpg_refs)
        self.tf_client.read_pi_from_switch = mock.Mock(
            return_value=physical_interface)

    def _mock_core_get_network(self, segmentation_id=100, net_type='vlan'):
        self.core_plugin.get_network = mock.Mock(
            return_value={'provider:segmentation_id': segmentation_id,
                          'provider:network_type': net_type})
