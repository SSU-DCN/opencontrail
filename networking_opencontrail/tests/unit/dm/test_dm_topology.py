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
import mock

from networking_opencontrail.dm.dm_topology import DmTopologyApi
from networking_opencontrail.dm.dm_topology import DmTopologyFile
from networking_opencontrail.dm.dm_topology import InvalidNodeError
from networking_opencontrail.dm.dm_topology import NodeNotFoundError
from networking_opencontrail.dm.dm_topology_loader import ConfigInvalidFormat
from networking_opencontrail.drivers.vnc_api_driver import VncApiClient
from networking_opencontrail.tests import base


@ddt.ddt
class DmTopologyApiTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF")
    def setUp(self, config):
        super(DmTopologyApiTestCase, self).setUp()

        self.tf_client = mock.Mock(spec_set=VncApiClient())

        self.dm_topology = DmTopologyApi(self.tf_client)
        self.dm_topology.initialize()

    def test_contains_host_true_when_in_api(self):
        self.tf_client.read_node_by_hostname = mock.Mock(
            return_value=mock.Mock())

        result = "compute1" in self.dm_topology

        self.tf_client.read_node_by_hostname.assert_called_with("compute1")
        self.assertEqual(True, result)

    @ddt.data('not-managed', None)
    def test_contains_host_false_when_not_in_api(self, host_id):
        self.tf_client.read_node_by_hostname = mock.Mock(return_value=None)

        result = host_id in self.dm_topology

        self.tf_client.read_node_by_hostname.assert_called_with(host_id)
        self.assertEqual(False, result)

    def test_get_node_from_api(self):
        self._mock_tf_client_node_in_api()

        node = self.dm_topology.get_node('host-2')

        expected_node = {'name': 'host-2',
                         'ports': [{'name': 'port-1',
                                    'switch_name': 'leaf2',
                                    'port_name': 'xe-1/1/1'},
                                   {'name': 'port-2',
                                    'switch_name': 'leaf2',
                                    'port_name': 'xe-2/2/2'}]}
        self.assertEqual(expected_node, node)
        tf_expected_calls = [
            mock.call.read_node_by_hostname('host-2'),
            mock.call.get_port(uuid='port-id-1'),
            mock.call.get_port(uuid='port-id-2')
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)

    def test_get_node_from_api_raise_when_no_node(self):
        self.tf_client.read_node_by_hostname = mock.Mock(return_value=None)

        self.assertRaises(NodeNotFoundError,
                          self.dm_topology.get_node,
                          'compute-1')

        self.tf_client.read_node_by_hostname.assert_called_with('compute-1')

    def test_get_node_from_api_raise_when_no_port_refs(self):
        node = mock.Mock(get_ports=mock.Mock(return_value=None))
        self.tf_client.read_node_by_hostname = mock.Mock(return_value=node)

        self.assertRaises(InvalidNodeError,
                          self.dm_topology.get_node,
                          'compute-1')

        self.tf_client.read_node_by_hostname.assert_called_with('compute-1')
        self.tf_client.get_port.assert_not_called()

    def test_get_node_from_api_raise_when_no_port(self):
        node = mock.Mock(get_ports=mock.Mock(
            return_value=[{'uuid': 'port-id-1'}]))
        self.tf_client.read_node_by_hostname = mock.Mock(return_value=node)
        self.tf_client.get_port = mock.Mock(return_value=None)

        self.assertRaises(InvalidNodeError,
                          self.dm_topology.get_node,
                          'compute-1')

        self.tf_client.read_node_by_hostname.assert_called_with('compute-1')
        self.tf_client.get_port.assert_called_with(uuid='port-id-1')

    def test_get_node_from_api_omits_ports_without_pi(self):
        self._mock_tf_client_node_in_api_with_port_without_pi_ref()

        node = self.dm_topology.get_node('host-2')

        expected_node = {'name': 'host-2',
                         'ports': [{'name': 'port-2',
                                    'switch_name': 'leaf2',
                                    'port_name': 'xe-2/2/2'}]}
        self.assertEqual(expected_node, node)
        tf_expected_calls = [
            mock.call.read_node_by_hostname('host-2'),
            mock.call.get_port(uuid='port-id-1'),
            mock.call.get_port(uuid='port-id-2')
        ]
        self.tf_client.assert_has_calls(tf_expected_calls)

    def test_get_node_from_api_raise_when_no_port_with_pi_ref(self):
        node = mock.Mock(get_ports=mock.Mock(
            return_value=[{'uuid': 'port-id-1'}]))
        port = mock.Mock()
        port.get_physical_interface_back_refs = mock.Mock(return_value=None)
        self.tf_client.read_node_by_hostname = mock.Mock(return_value=node)
        self.tf_client.get_port = mock.Mock(return_value=port)

        self.assertRaises(InvalidNodeError,
                          self.dm_topology.get_node,
                          'compute-1')

        self.tf_client.read_node_by_hostname.assert_called_with('compute-1')
        self.tf_client.get_port.assert_called_with(uuid='port-id-1')

    def _mock_tf_client_node_in_api(self):
        pi_1 = mock.Mock(fq_name=['default-config', 'leaf2', 'xe-1/1/1'])
        port_1 = mock.Mock(fq_name=['parent', 'port-1'])
        port_1.get_physical_interface_back_refs = mock.Mock(
            return_value=[{'to': pi_1.fq_name}])
        pi_2 = mock.Mock(fq_name=['default-config', 'leaf2', 'xe-2/2/2'])
        port_2 = mock.Mock(fq_name=['parent', 'port-2'])
        port_2.get_physical_interface_back_refs = mock.Mock(
            return_value=[{'to': pi_2.fq_name}])
        node = mock.Mock(get_ports=mock.Mock(
            return_value=[{'uuid': 'port-id-1'}, {'uuid': 'port-id-2'}]))

        self.tf_client.read_node_by_hostname = mock.Mock(return_value=node)
        self.tf_client.get_port = mock.Mock(side_effect=[port_1, port_2])

    def _mock_tf_client_node_in_api_with_port_without_pi_ref(self):
        port_1 = mock.Mock(fq_name=['parent', 'port-1'])
        port_1.get_physical_interface_back_refs = mock.Mock(return_value=None)
        pi_2 = mock.Mock(fq_name=['default-config', 'leaf2', 'xe-2/2/2'])
        port_2 = mock.Mock(fq_name=['parent', 'port-2'])
        port_2.get_physical_interface_back_refs = mock.Mock(
            return_value=[{'to': pi_2.fq_name}])
        node = mock.Mock(get_ports=mock.Mock(
            return_value=[{'uuid': 'port-id-1'}, {'uuid': 'port-id-2'}]))

        self.tf_client.read_node_by_hostname = mock.Mock(return_value=node)
        self.tf_client.get_port = mock.Mock(side_effect=[port_1, port_2])


@ddt.ddt
class DmTopologyFileTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF")
    def setUp(self, config):
        super(DmTopologyFileTestCase, self).setUp()

        self.dm_topology = DmTopologyFile('path/')
        self.dm_topology.topology_loader.load = mock.Mock(
            return_value=self._get_topology())
        self.dm_topology.initialize()

    @mock.patch("networking_opencontrail.dm.dm_topology.DmTopologyLoader")
    def test_file_topology_is_loaded_on_initializing(self, loader):
        topology = mock.Mock()
        loader().load = mock.Mock(return_value=topology)
        dm_topology = DmTopologyFile('path/')

        dm_topology.initialize()

        self.assertEqual(dm_topology.topology, topology)

    def test_file_topology_should_be_validated_on_initializing(self):
        self.dm_topology.topology_loader.load = \
            mock.Mock(side_effect=ConfigInvalidFormat)
        self.assertRaises(ConfigInvalidFormat, self.dm_topology.initialize)

    def test_contains_host_true_when_in_topology_file(self):
        result = "compute1" in self.dm_topology
        self.assertEqual(True, result)

    @ddt.data('not-managed', None)
    def test_contains_host_false_when_not_in_topology_file(self, host_id):
        result = host_id in self.dm_topology
        self.assertEqual(False, result)

    def test_get_node_from_file(self):
        node = self.dm_topology.get_node('compute1')

        expected_node = {'name': 'compute1',
                         'ports': [{'name': 'ens1f1',
                                    'switch_name': 'leaf1',
                                    'port_name': 'xe-0/0/1'}]}
        self.assertEqual(expected_node, node)

    @ddt.data('not-managed', None)
    def test_get_node_from_file_raise_when_not_in_topology(self, host_id):
        self.assertRaises(NodeNotFoundError,
                          self.dm_topology.get_node,
                          host_id)

    def _get_topology(self):
        switch_port = {'name': 'ens1f1', 'switch_name': 'leaf1',
                       'port_name': 'xe-0/0/1'}
        return {'compute1': {'name': 'compute1', 'ports': [switch_port]}}
