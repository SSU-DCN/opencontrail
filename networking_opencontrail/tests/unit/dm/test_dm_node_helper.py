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
import ddt
import json

import mock

from networking_opencontrail.dm.dm_node_helper import DmNodeHelper
from networking_opencontrail.dm.dm_node_helper import FabricNotFoundError
from networking_opencontrail.dm.dm_node_helper import NodeNotFoundError
from networking_opencontrail.dm.dm_topology_loader import ConfigInvalidFormat
from networking_opencontrail.drivers.vnc_api_driver import VncApiClient
from networking_opencontrail.tests import base


@ddt.ddt
class DmNodeHelperTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF",
                DM_INTEGRATION=mock.MagicMock(enabled=True))
    def setUp(self, config):
        super(DmNodeHelperTestCase, self).setUp()
        self.tf_client = mock.Mock(spec_set=VncApiClient())

        self.helper = DmNodeHelper(self.tf_client)
        self.helper.topology_loader.load = mock.Mock(
            return_value=self._get_topology())
        self.helper.initialize()

        def tearDown(self):
            super(DmNodeHelperTestCase, self).tearDown()

    @mock.patch("networking_opencontrail.dm.dm_node_helper"
                ".DmTopologyLoader")
    def test_topology_is_loaded_on_initializing(self, loader):
        topology = mock.Mock()
        loader().load = mock.Mock(return_value=topology)
        helper = DmNodeHelper(self.tf_client)

        helper.initialize()

        self.assertEqual(helper.topology, topology)

    def test_topology_should_be_validated_on_initializing(self):
        self.helper.topology_loader.load = \
            mock.Mock(side_effect=ConfigInvalidFormat)
        self.assertRaises(ConfigInvalidFormat, self.helper.initialize)

    def test_check_node_managed_true_when_in_topology_file(self):
        result = self.helper.check_node_managed("compute1")
        self.assertEqual(True, result)

    @ddt.data('not-managed', None)
    def test_check_node_managed_false_when_not_in_topology_file(self, host_id):
        result = self.helper.check_node_managed(host_id)
        self.assertEqual(False, result)

    def test_get_bindings_for_node_when_first_in_vpg(self):
        self._mock_tf_client_when_no_vpg()
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_node('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch("leaf1"),
            mock.call.read_pi_from_switch("leaf1", "xe-0/0/1"),
            mock.call.make_key_value_pairs(expected_bindings)
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.assertEqual(tf_kvpairs, bindings)

    def test_get_bindings_for_node_when_only_maually_vpg_exist(self):
        """Don't connect to VPGs created manually by someone."""
        self._mock_tf_client_when_only_manually_created_vpg_exists()
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_node('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch("leaf1"),
            mock.call.read_pi_from_switch("leaf1", "xe-0/0/1"),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.make_key_value_pairs(expected_bindings),
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.assertEqual(tf_kvpairs, bindings)

    def test_get_bindings_for_node_when_exists_autocreated_vpg(self):
        self._mock_tf_client_when_autocreated_vpg_exists()
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_node('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal'),
                             ('vpg', 'vpg-2')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch("leaf1"),
            mock.call.read_pi_from_switch("leaf1", "xe-0/0/1"),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.get_virtual_port_group(uuid='vpg-id-2'),
            mock.call.make_key_value_pairs(expected_bindings),
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.assertEqual(tf_kvpairs, bindings)

    def test_get_bindings_for_node_raise_when_no_fabric_name(self):
        self._mock_tf_client_read_fabric_name(None)

        self.assertRaises(FabricNotFoundError,
                          self.helper.get_bindings_for_node,
                          'compute1')

        self.tf_client.read_fabric_name_from_switch.assert_called_with("leaf1")

    @ddt.data('not-managed', None)
    def test_get_bindings_raise_when_no_node_in_topology(self, host_id):
        self.assertRaises(NodeNotFoundError,
                          self.helper.get_bindings_for_node,
                          host_id)
        self.tf_client.assert_not_called()

    def _get_topology(self):
        switch_port = {'name': 'ens1f1', 'switch_name': 'leaf1',
                       'port_name': 'xe-0/0/1'}
        return {'nodes': [{'name': 'compute1', 'ports': [switch_port]}]}

    def _mock_tf_client_when_no_vpg(self):
        self._mock_tf_client_physical_interface(vpg_refs=None)

    def _mock_tf_client_when_only_manually_created_vpg_exists(self):
        """Mock existing one, manually-created VPG"""
        vpg_1 = mock.Mock(fq_name=['parent-name', 'vpg-1'], uuid='vpg-id-1')
        vpg_1.get_virtual_port_group_user_created = mock.Mock(
            return_value=True)
        self.tf_client.get_virtual_port_group = mock.Mock(side_effect=[vpg_1])

        vpg_refs = [{'to': vpg_1.fq_name, 'uuid': vpg_1.uuid}]
        self._mock_tf_client_physical_interface(vpg_refs)

    def _mock_tf_client_when_autocreated_vpg_exists(self):
        """Mock existing two VPGs: one manually created, one auto-generated"""
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

    def _mock_tf_client_read_fabric_name(self, fabric_name="fabric-1"):
        self.tf_client.read_fabric_name_from_switch = mock.Mock(
            return_value=fabric_name)

    def _mock_tf_client_make_key_value_pairs(self):
        kv_pairs = mock.Mock()
        self.tf_client.make_key_value_pairs = mock.Mock(return_value=kv_pairs)
        return kv_pairs
