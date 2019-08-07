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

import ddt
import mock

from networking_opencontrail.dm import dm_integrator
from networking_opencontrail.drivers.vnc_api_driver import VncApiClient
from networking_opencontrail.tests import base


@ddt.ddt
class DeviceManagerIntegratorTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF",
                DM_INTEGRATION=mock.MagicMock(enabled=True))
    @mock.patch("networking_opencontrail.dm.dm_integrator.DmNodeHelper")
    def setUp(self, node_helper, config):
        super(DeviceManagerIntegratorTestCase, self).setUp()
        dm_integrator.directory.get_plugin = mock.Mock()
        dm_integrator.VncApiClient = mock.Mock(spec_set=VncApiClient)

        self.dm_integrator = dm_integrator.DeviceManagerIntegrator()
        self.dm_integrator.initialize()

        self.core_plugin = self.dm_integrator._core_plugin
        self.tf_client = self.dm_integrator.tf_client
        self.node_helper = self.dm_integrator.node_helper

    def tearDown(self):
        super(DeviceManagerIntegratorTestCase, self).tearDown()

    def test_enabled_when_config_set(self):
        with mock.patch("oslo_config.cfg.CONF",
                        DM_INTEGRATION=mock.MagicMock(enabled=True)):
            self.assertEqual(self.dm_integrator.enabled, True)

        with mock.patch("oslo_config.cfg.CONF",
                        DM_INTEGRATION=mock.MagicMock(enabled=False)):
            self.assertEqual(self.dm_integrator.enabled, False)

    @mock.patch("oslo_config.cfg.CONF",
                DM_INTEGRATION=mock.MagicMock(enabled=False))
    @mock.patch("networking_opencontrail.dm.dm_integrator"
                ".DmNodeHelper")
    def test_node_helper_is_not_initialized_when_disabled(self, helper, conf):
        integrator = dm_integrator.DeviceManagerIntegrator()

        integrator.initialize()

        helper().initialize.assert_not_called()

    @mock.patch("oslo_config.cfg.CONF",
                DM_INTEGRATION=mock.MagicMock(enabled=True))
    @mock.patch("networking_opencontrail.dm.dm_integrator"
                ".DmNodeHelper")
    def test_node_helper_is_loaded_on_initializing(self, helper, conf):
        integrator = dm_integrator.DeviceManagerIntegrator()

        integrator.initialize()

        helper().initialize.assert_called_once()

    @ddt.data(1, 100, 4094)
    def test_create_tagging_for_port(self, vlan_tag):
        self._mock_core_get_network(segmentation_id=vlan_tag)
        self._mock_node_helper_check_node_managed()
        bindings = self._mock_node_helper_get_bindings()
        self._mock_tf_client_get_vmi(None)
        tf_project = self._mock_tf_client_get_project()
        tf_vn = self._mock_tf_client_get_vn()
        tf_properties = self._mock_tf_client_make_vmi_properties()
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
        tf_expected_calls = [
            mock.call.get_project(
                str(uuid.UUID("12345678123456781234567812345678"))),
            mock.call.get_virtual_machine_interface(
                fq_name=tf_project.fq_name + [expected_vmi_name]),
            mock.call.get_virtual_network("net-1"),
            mock.call.make_vmi_properties_with_vlan_tag(vlan_tag),
            mock.call.make_virtual_machine_interface(
                expected_vmi_name, tf_vn, tf_properties,
                bindings, tf_project),
            mock.call.create_virtual_machine_interface(tf_created_vmi)
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        node_helper_expected_calls = [
            mock.call.check_node_managed('compute1'),
            mock.call.get_bindings_for_node('compute1')
        ]
        self.node_helper.assert_has_calls(node_helper_expected_calls)
        self.core_plugin.get_network.assert_called_with(context, "net-1")

    @ddt.data({'binding:host_id': 'not-managed', 'device_id': 'vm-1'},
              {'device_id': 'vm-1'})
    def test_not_created_tagging_when_node_not_managed(self, port_data):
        context = self._get_fake_context()
        self._mock_node_helper_check_node_managed(False)

        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.node_helper.check_node_managed.assert_called_with(
            port_data.get('binding:host_id'))
        self.tf_client.assert_not_called()
        self.core_plugin.assert_not_called()

    @ddt.data(None, 0, 4095)
    def test_not_created_tagging_when_invalid_vlan(self, invalid_tag):
        context = self._get_fake_context()
        self._mock_core_get_network(segmentation_id=invalid_tag)
        self._mock_node_helper_check_node_managed()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.node_helper.check_node_managed.assert_called_with('compute1')
        self.core_plugin.get_network.assert_called_with(context, "net-1")
        self.tf_client.assert_not_called()

    def test_not_created_tagging_when_network_not_vlan(self):
        context = self._get_fake_context()
        self._mock_core_get_network(net_type='not-vlan')
        self._mock_node_helper_check_node_managed()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'device_id': 'vm-1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}

        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.node_helper.check_node_managed.assert_called_with('compute1')
        self.core_plugin.get_network.assert_called_with(context, "net-1")
        self.tf_client.assert_not_called()

    def test_not_created_tagging_when_no_device_id(self):
        self._mock_core_get_network()
        context = self._get_fake_context()
        self._mock_node_helper_check_node_managed()

        port_data = {'network_id': 'net-1',
                     'binding:host_id': 'compute1',
                     'tenant_id': '12345678123456781234567812345678',
                     'id': 'port-1'}
        self.dm_integrator.create_vlan_tagging_for_port(
            context, {'port': port_data})

        self.node_helper.check_node_managed.assert_called_with('compute1')
        self.tf_client.create_virtual_machine_interface.assert_not_called()

    def test_not_created_tagging_when_vn_not_exists_in_tf(self):
        context = self._get_fake_context()
        self._mock_core_get_network()
        self._mock_node_helper_check_node_managed()
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
        self.node_helper.check_node_managed.assert_called_with('compute1')
        self.core_plugin.get_network.assert_called_with(context, "net-1")

    def test_use_existing_vmi_on_create_tagging(self):
        self._mock_core_get_network()
        self._mock_node_helper_check_node_managed()
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
        self.node_helper.check_node_managed.assert_called_with('compute1')
        self.core_plugin.get_network.assert_called_with(context, "net-1")
        self.tf_client.create_virtual_machine_interface.assert_not_called()

    def test_delete_tagging(self):
        self._mock_node_helper_check_node_managed()
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
        self.node_helper.check_node_managed.assert_called_with('compute1')

    def test_delete_tagging_when_no_vpg_refs(self):
        self._mock_node_helper_check_node_managed()
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
        self.node_helper.check_node_managed.assert_called_with('compute1')

    @ddt.data({'binding:host_id': 'not-managed', 'device_id': 'vm-1'},
              {'device_id': 'vm-1'})
    def test_not_try_delete_tagging_when_node_not_managed(self, port_data):
        self._mock_node_helper_check_node_managed(False)

        self.dm_integrator.delete_vlan_tagging_for_port(port_data)

        self.node_helper.check_node_managed.assert_called_with(
            port_data.get('binding:host_id'))
        self.tf_client.assert_not_called()

    def test_not_try_delete_tagging_when_no_vmi(self):
        self._mock_node_helper_check_node_managed()
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
        self.node_helper.check_node_managed.assert_called_with('compute1')

    def _get_topology(self):
        switch_port = {'name': 'ens1f1', 'switch_name': 'leaf1',
                       'port_name': 'xe-0/0/1'}
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

    def _mock_node_helper_check_node_managed(self, value=True):
        self.node_helper.check_node_managed = mock.Mock(return_value=value)

    def _mock_node_helper_get_bindings(self):
        binding = mock.Mock()
        self.node_helper.get_bindings_for_node = mock.Mock(
            return_value=binding)
        return binding

    def _mock_node_helper_raise(self, exc):
        self.node_helper.get_bindings_for_node = mock.Mock(side_effect=exc)

    def _mock_core_get_network(self, segmentation_id=100, net_type='vlan'):
        self.core_plugin.get_network = mock.Mock(
            return_value={'provider:segmentation_id': segmentation_id,
                          'provider:network_type': net_type})
