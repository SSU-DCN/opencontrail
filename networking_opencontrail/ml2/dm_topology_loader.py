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

from jsonschema import validate
from jsonschema import ValidationError
from oslo_config import cfg

import yaml


class DmTopologyLoader(object):

    def load(self):
        if cfg.CONF.DM_INTEGRATION.topology:
            topology = self._load_yaml_file(cfg.CONF.DM_INTEGRATION.topology)
            self.validate(topology)
            return topology
        else:
            raise NoTopologyFileError

    def validate(self, config):
        """Validates config. Expected format is dict.

        Example of valid config:
        {'nodes': [
            {'name': 'b1s19-node3',
             'type': 'baremetal',
             'ports': [
                 {'name': 'ens1f1',
                  'switch_name': 'vqfx-10k-leaf2',
                  'port_name': 'xe-0/0/1',
                  'switch_id': '52:54:00:29:b1:a6'}
             ]}
        ]}
        """

        schema = """
        type: object
        required:
        - nodes
        properties:
          nodes:
            type: array
            items:
              type: object
              required:
              - name
              - ports
              properties:
                name:
                  type: string
                ports:
                  type: array
                  items:
                    type: object
                    required:
                    - switch_name
                    - port_name
                    - switch_id
                    properties:
                      name:
                        type: string
                      switch_name:
                        type: string
                      port_name:
                        type: string
                      switch_id:
                        type: string
                """

        try:
            validate(config, yaml.load(schema))
        except ValidationError as e:
            raise ConfigInvalidFormat(e)

    def _load_yaml_file(self, topology_filename):
        with open(topology_filename, "r") as topology_yaml:
            return yaml.load(topology_yaml)


class ConfigInvalidFormat(Exception):
    pass


class NoTopologyFileError(Exception):
    pass
