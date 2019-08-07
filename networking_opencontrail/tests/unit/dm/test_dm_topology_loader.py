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

from networking_opencontrail.dm import dm_topology_loader
from networking_opencontrail.dm.dm_topology_loader import ConfigInvalidFormat
from networking_opencontrail.tests import base


def _get_topology():
    switch_port = {'name': 'ens1f1',
                   'switch_name': 'leaf1',
                   'port_name': 'xe-0/0/1'}
    return {'nodes': [{'name': 'compute1', 'ports': [switch_port]}]}


class TestDmTopologyLoader(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF",
                DM_INTEGRATION=mock.MagicMock(topology=None))
    def setUp(self, conf):
        super(TestDmTopologyLoader, self).setUp()
        self.dm_topology_loader = dm_topology_loader.DmTopologyLoader()

    @mock.patch("oslo_config.cfg.CONF",
                DM_INTEGRATION=mock.MagicMock(topology='path/'))
    def test_correct_topology_should_return_dict(self, _):
        yaml_file = _get_topology()
        self.dm_topology_loader._load_yaml_file = mock.Mock(
            return_value=yaml_file)

        actual = self.dm_topology_loader.load()

        self.assertEqual(yaml_file, actual)
        self.dm_topology_loader._load_yaml_file.assert_called_with('path/')

    @mock.patch("oslo_config.cfg.CONF")
    def test_duplicated_node_names_should_raise_exception(self, _):
        yaml_file = _get_topology()
        port = {'name': 'port-2',
                'switch_name': 'leaf2',
                'port_name': 'xe-0/1/1'}
        yaml_file['nodes'].append({'name': 'compute1', 'ports': [port]})

        self.dm_topology_loader._load_yaml_file = mock.Mock(
            return_value=yaml_file)

        self.assertRaises(ConfigInvalidFormat, self.dm_topology_loader.load)

    @mock.patch("oslo_config.cfg.CONF")
    def test_invalid_schema_should_raise_exception(self, _):
        yaml_file = _get_topology()
        del yaml_file['nodes'][0]['name']

        self.dm_topology_loader._load_yaml_file = mock.Mock(
            return_value=yaml_file)

        self.assertRaises(ConfigInvalidFormat, self.dm_topology_loader.load)

    @mock.patch("oslo_config.cfg.CONF")
    def test_empty_topology_file_should_return_empty_dict(self, _):
        self.dm_topology_loader._load_yaml_file = mock.Mock(return_value={})

        self.assertRaises(ConfigInvalidFormat, self.dm_topology_loader.load)

    @mock.patch("oslo_config.cfg.CONF")
    def test_no_file_should_raise_exception(self, config):
        config.DM_INTEGRATION = mock.Mock()
        config.DM_INTEGRATION.topology = '/file_does_not_exist'

        self.assertRaises(IOError, self.dm_topology_loader.load)

    @mock.patch("oslo_config.cfg.CONF")
    def test_no_file_path_should_return_none(self, config):
        config.DM_INTEGRATION = mock.Mock()
        config.DM_INTEGRATION.topology = None

        actual = self.dm_topology_loader.load()

        self.assertIsNone(actual)

    @mock.patch("oslo_config.cfg.CONF")
    @mock.patch("networking_opencontrail.dm.dm_topology_loader.yaml")
    def test_load_yaml_file_loads_right_file(self, yaml, _):
        yaml.safe_load = mock.Mock(return_value='loaded')

        with mock.patch("networking_opencontrail.dm.dm_topology_loader.open",
                        mock.mock_open(), create=True) as mocked_open:
            value = self.dm_topology_loader._load_yaml_file('path/to/file')

            mocked_open.assert_called_with('path/to/file', 'r')
            yaml.safe_load.assert_called_with(mocked_open())
            self.assertEqual('loaded', value)
