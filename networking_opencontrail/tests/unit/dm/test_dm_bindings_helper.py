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

import ddt
import mock

from oslo_config import cfg

from networking_opencontrail.dm.dm_bindings_helper import DmBindingsHelper
from networking_opencontrail.dm.dm_bindings_helper import FabricNotFoundError
from networking_opencontrail.dm.dm_bindings_helper import \
    PhysicalInterfaceNotFoundError
from networking_opencontrail.dm.dm_topology import DmTopologyFile
from networking_opencontrail.drivers.vnc_api_driver import VncApiClient
from networking_opencontrail.tests import base


@ddt.ddt
class DmBindingsHelperTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF")
    @mock.patch("networking_opencontrail.dm.dm_bindings_helper.DmTopologyFile")
    def setUp(self, topology, config):
        super(DmBindingsHelperTestCase, self).setUp()
        self.tf_client = mock.Mock(spec_set=VncApiClient())
        self.dm_topology = mock.Mock(spec_set=DmTopologyFile)
        topology.return_value = self.dm_topology

        self.helper = DmBindingsHelper(self.tf_client)
        self.helper.initialize()

    @mock.patch("oslo_config.cfg.CONF")
    @mock.patch("networking_opencontrail.dm.dm_bindings_helper.DmTopologyFile")
    def test_topology_is_initialized_on_initializing(self, topology, config):
        helper = DmBindingsHelper(self.tf_client)

        helper.initialize()

        topology.assert_called_with(cfg.CONF.DM_INTEGRATION.topology)
        topology().initialize.assert_called()

    def test_check_host_managed_true_when_dm_topology_true(self):
        self.dm_topology.__contains__ = mock.Mock(return_value=True)

        result = self.helper.check_host_managed('compute1')

        self.assertEqual(True, result)
        self.dm_topology.__contains__.assert_called_with('compute1')

    def test_check_host_managed_false_when_dm_topology_false(self):
        self.dm_topology.__contains__ = mock.Mock(return_value=False)

        result = self.helper.check_host_managed('compute1')

        self.assertEqual(False, result)
        self.dm_topology.__contains__.assert_called_with('compute1')

    def test_get_bindings_for_host_when_first_in_vpg(self):
        self._mock_get_node()
        self._mock_tf_client_when_no_vpg()
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_host('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'},
                                     {'port_id': 'xe-0/0/2',
                                      'switch_info': 'leaf2',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch('leaf1'),
            mock.call.read_fabric_name_from_switch('leaf2'),
            mock.call.read_pi_from_switch('leaf1', 'xe-0/0/1'),
            mock.call.make_key_value_pairs(expected_bindings)
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.dm_topology.get_node.assert_called_with('compute1')
        self.assertEqual(tf_kvpairs, bindings)

    def test_get_bindings_for_host_when_only_maually_vpg_exist(self):
        """Don't connect to VPGs created manually by someone."""
        self._mock_get_node()
        self._mock_tf_client_when_only_manually_created_vpg_exists()
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_host('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'},
                                     {'port_id': 'xe-0/0/2',
                                      'switch_info': 'leaf2',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch('leaf1'),
            mock.call.read_fabric_name_from_switch('leaf2'),
            mock.call.read_pi_from_switch('leaf1', 'xe-0/0/1'),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.make_key_value_pairs(expected_bindings),
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.dm_topology.get_node.assert_called_with('compute1')
        self.assertEqual(tf_kvpairs, bindings)

    @ddt.data([{'to': ['config', 'leaf1', 'xe-0/0/1']}], None)
    def test_get_bindings_for_host_when_vpg_has_invalid_refs(self, vpg_refs):
        """When VPG doesn't have refs to all required PIs, don't use it"""
        self._mock_get_node()
        self._mock_tf_client_when_autocreated_invalid_vpg_exists(vpg_refs)
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_host('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'},
                                     {'port_id': 'xe-0/0/2',
                                      'switch_info': 'leaf2',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch('leaf1'),
            mock.call.read_fabric_name_from_switch('leaf2'),
            mock.call.read_pi_from_switch('leaf1', 'xe-0/0/1'),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.make_key_value_pairs(expected_bindings),
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.dm_topology.get_node.assert_called_with('compute1')
        self.assertEqual(tf_kvpairs, bindings)

    def test_get_bindings_for_host_when_exists_autocreated_vpg(self):
        self._mock_get_node()
        self._mock_tf_client_when_autocreated_vpg_exists()
        self._mock_tf_client_read_fabric_name()
        tf_kvpairs = self._mock_tf_client_make_key_value_pairs()

        bindings = self.helper.get_bindings_for_host('compute1')

        expected_binding_profile = {'local_link_information':
                                    [{'port_id': 'xe-0/0/1',
                                      'switch_info': 'leaf1',
                                      'fabric': 'fabric-1'},
                                     {'port_id': 'xe-0/0/2',
                                      'switch_info': 'leaf2',
                                      'fabric': 'fabric-1'}]}
        expected_bindings = [('profile', json.dumps(expected_binding_profile)),
                             ('vnic_type', 'baremetal'),
                             ('vpg', 'vpg-2')]
        tf_expected_calls = [
            mock.call.read_fabric_name_from_switch('leaf1'),
            mock.call.read_fabric_name_from_switch('leaf2'),
            mock.call.read_pi_from_switch('leaf1', 'xe-0/0/1'),
            mock.call.get_virtual_port_group(uuid='vpg-id-1'),
            mock.call.get_virtual_port_group(uuid='vpg-id-2'),
            mock.call.make_key_value_pairs(expected_bindings),
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)
        self.dm_topology.get_node.assert_called_with('compute1')
        self.assertEqual(tf_kvpairs, bindings)

    def test_get_bindings_for_host_raise_when_no_fabric_name(self):
        self._mock_get_node()
        self._mock_tf_client_read_fabric_name(None)

        self.assertRaises(FabricNotFoundError,
                          self.helper.get_bindings_for_host,
                          'compute1')

        self.tf_client.read_fabric_name_from_switch.assert_called_with('leaf1')
        self.dm_topology.get_node.assert_called_with('compute1')

    def test_get_bindings_for_host_raise_when_pi_not_exist(self):
        self._mock_get_node()
        self._mock_tf_client_read_fabric_name()
        self.tf_client.read_pi_from_switch = mock.Mock(return_value=None)

        self.assertRaises(PhysicalInterfaceNotFoundError,
                          self.helper.get_bindings_for_host,
                          'compute1')

        self.tf_client.read_pi_from_switch('leaf1', 'xe-0/0/1')
        self.dm_topology.get_node.assert_called_with('compute1')

    def _mock_get_node(self):
        switch_port_1 = {'name': 'ens1f1', 'switch_name': 'leaf1',
                         'port_name': 'xe-0/0/1'}
        switch_port_2 = {'name': 'ens1f2', 'switch_name': 'leaf2',
                         'port_name': 'xe-0/0/2'}
        node = {'name': 'compute1', 'ports': [switch_port_1, switch_port_2]}
        self.dm_topology.get_node.return_value = node

    def _mock_get_node_none(self):
        self.dm_topology.get_node.return_value = None

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
        vpg_2_pi_refs = [{'to': ['config', 'leaf1', 'xe-0/0/1']},
                         {'to': ['config', 'leaf2', 'xe-0/0/2']}]
        vpg_2.get_physical_interface_refs = mock.Mock(
            return_value=vpg_2_pi_refs)
        vpg_2.get_virtual_port_group_user_created = mock.Mock(
            return_value=False)
        self.tf_client.get_virtual_port_group = mock.Mock(
            side_effect=[vpg_1, vpg_2])

        vpg_refs = [{'to': vpg_1.fq_name, 'uuid': vpg_1.uuid},
                    {'to': vpg_2.fq_name, 'uuid': vpg_2.uuid}]
        self._mock_tf_client_physical_interface(vpg_refs)

    def _mock_tf_client_when_autocreated_invalid_vpg_exists(self, vpg_pi_refs):
        """Mock VPG that doesn't have refs to all related PIs"""
        vpg = mock.Mock(fq_name=['parent-name', 'vpg-1'], uuid='vpg-id-1')
        vpg.get_physical_interface_refs = mock.Mock(
            return_value=vpg_pi_refs)
        vpg.get_virtual_port_group_user_created = mock.Mock(
            return_value=False)
        self.tf_client.get_virtual_port_group = mock.Mock(
            side_effect=[vpg])

        vpg_refs = [{'to': vpg.fq_name, 'uuid': vpg.uuid}]
        self._mock_tf_client_physical_interface(vpg_refs)

    def _mock_tf_client_physical_interface(self, vpg_refs):
        physical_interface = mock.Mock()
        physical_interface.get_virtual_port_group_back_refs = mock.Mock(
            return_value=vpg_refs)
        self.tf_client.read_pi_from_switch = mock.Mock(
            return_value=physical_interface)

    def _mock_tf_client_read_fabric_name(self, fabric_name='fabric-1'):
        self.tf_client.read_fabric_name_from_switch = mock.Mock(
            return_value=fabric_name)

    def _mock_tf_client_make_key_value_pairs(self):
        kv_pairs = mock.Mock()
        self.tf_client.make_key_value_pairs = mock.Mock(return_value=kv_pairs)
        return kv_pairs
