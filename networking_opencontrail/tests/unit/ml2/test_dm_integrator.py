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

import mock

from networking_opencontrail.ml2 import dm_integrator
from networking_opencontrail.ml2.dm_topology_loader import ConfigInvalidFormat
from networking_opencontrail.tests import base


class DeviceManagerIntegratorTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF",
                APISERVER=mock.MagicMock(topology=None))
    def setUp(self, config):
        super(DeviceManagerIntegratorTestCase, self).setUp()
        dm_integrator.directory.get_plugin = mock.Mock()
        dm_integrator.ContrailRestApiDriver = mock.Mock()

        self.dm_integrator = dm_integrator.DeviceManagerIntegrator()
        self.dm_integrator.topology_loader.load = mock.Mock(
            return_value=self._get_topology())
        self.dm_integrator.initialize()

        self.core_plugin = self.dm_integrator._core_plugin
        self.tf_rest_driver = self.dm_integrator.tf_rest_driver

    def tearDown(self):
        super(DeviceManagerIntegratorTestCase, self).tearDown()

    @mock.patch("oslo_config.cfg.CONF")
    def test_topology_should_be_validated_on_initializing(self, _):
        self.dm_integrator.topology_loader.load = \
            mock.Mock(side_effect=ConfigInvalidFormat)
        self.assertRaises(ConfigInvalidFormat, self.dm_integrator.initialize)

    def test_enable_vlan_taging_on_port(self):
        self._mock_core_get_network()
        context = self._get_fake_context()
        port_data = {'network_id': 'net-1'}

        self.dm_integrator.enable_vlan_tag_on_port(
            context, {'port': port_data})

        expected_properties = {'sub_interface_vlan_tag': '100'}
        self.assertEqual(expected_properties,
                         port_data['virtual_machine_interface_properties'])
        self.assertEqual('baremetal', port_data['binding:vnic_type'])

    def test_add_binding_to_first_port_in_vpg(self):
        self._mock_tf_rest_calls_when_no_vpg()
        port_data = {'binding:host_id': 'compute1'}

        self.dm_integrator.add_port_binding_to_port({'port': port_data})

        expected_link = {'port_id': 'xe-0/0/1',
                         'switch_id': 'mac-address',
                         'switch_info': 'leaf1',
                         'fabric': 'fab01'}
        expected_binding_profile = {'local_link_information': [expected_link]}
        self.assertDictEqual(expected_binding_profile,
                             port_data['binding:profile'])
        self.assertEqual('baremetal', port_data['binding:vnic_type'])

    def test_add_binding_and_existing_vpg(self):
        self._mock_tf_rest_calls_when_vpg_exists()
        port_data = {'binding:host_id': 'compute1'}

        self.dm_integrator.add_port_binding_to_port({'port': port_data})

        expected_link = {'port_id': 'xe-0/0/1',
                         'switch_id': 'mac-address',
                         'switch_info': 'leaf1',
                         'fabric': 'fab01'}
        expected_binding_profile = {'local_link_information': [expected_link]}
        self.assertDictEqual(expected_binding_profile,
                             port_data['binding:profile'])
        self.assertEqual('baremetal', port_data['binding:vnic_type'])
        self.assertEqual('vpg-1', port_data['binding:vpg'])

    def test_not_add_binding_when_host_not_in_topology(self):
        self.tf_rest_driver = mock.Mock()
        port_data = {'binding:host_id': 'invalid-host'}

        self.dm_integrator.add_port_binding_to_port({'port': port_data})

        self.assertNotIn('binding:profile', port_data)
        self.assertNotIn('binding:vnic_type', port_data)
        self.tf_rest_driver.assert_not_called()

    def test_not_add_binding_when_no_host(self):
        self.tf_rest_driver = mock.Mock()
        port_data = {}

        self.dm_integrator.add_port_binding_to_port({'port': port_data})

        self.assertNotIn('binding:profile', port_data)
        self.assertNotIn('binding:vnic_type', port_data)
        self.tf_rest_driver.assert_not_called()

    def _get_topology(self):
        switch_port = {'name': 'ens1f1', 'switch_name': 'leaf1',
                       'port_name': 'xe-0/0/1', 'switch_id': 'mac-address',
                       'fabric': 'fab01'}
        return {'nodes': [{'name': 'compute1', 'ports': [switch_port]}]}

    def _get_fake_context(self, **kwargs):
        return mock.Mock(**kwargs)

    def _get_fake_physical_int(self):
        return {'fq_name': ['xe-0/0/1'], 'uuid': 'id-1'}

    def _mock_tf_rest_calls_when_no_vpg(self):
        physical_interface = self._get_fake_physical_int()
        self._mock_tf_rest_physical_int(physical_interface)

    def _mock_tf_rest_calls_when_vpg_exists(self):
        physical_interface = self._get_fake_physical_int()
        physical_interface.update(
            {'virtual_port_group_back_refs': [{'to': ['vpg-1']}]})
        self._mock_tf_rest_physical_int(physical_interface)

    def _mock_tf_rest_physical_int(self, physical_interface):
        list_physical_interfaces = [
            None, {"physical-interfaces": [physical_interface]}]
        get_physical_interface = [
            None, {'physical-interface': physical_interface}]

        self.tf_rest_driver.list_resource = mock.Mock(
            return_value=list_physical_interfaces)
        self.tf_rest_driver.get_resource = mock.Mock(
            return_value=get_physical_interface)

    def _mock_core_get_network(self):
        self.core_plugin.get_network = mock.Mock(
            return_value={'provider:segmentation_id': '100'})
