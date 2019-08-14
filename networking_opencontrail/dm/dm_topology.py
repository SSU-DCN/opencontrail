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

from oslo_log import log as logging

from networking_opencontrail.dm.dm_topology_loader import DmTopologyLoader

LOG = logging.getLogger(__name__)


class DmTopology(object):
    def __init__(self, tf_client):
        self.topology_loader = DmTopologyLoader()
        self.tf_client = tf_client
        self.topology = None

    def __contains__(self, host_id):
        if self._file_loaded:
            return self._get_node_from_topology_file(host_id) is not None
        return self._check_node_exists_in_api(host_id)

    def initialize(self):
        self.topology = self.topology_loader.load()

    def get_node(self, host_id):
        if self._file_loaded:
            node = self._get_node_from_topology_file(host_id)
            if not node:
                LOG.error("Try to get node for host %s, but node not found" %
                          host_id)
                raise NodeNotFoundError
            return node
        return self._get_node_from_api(host_id)

    def _check_node_exists_in_api(self, host_id):
        vnc_node = self.tf_client.read_node_by_hostname(host_id)
        return vnc_node is not None

    def _get_node_from_topology_file(self, host_id):
        nodes = [n for n in self.topology['nodes'] if n['name'] == host_id]
        if len(nodes) == 1:
            return nodes[0]
        return None

    def _get_node_from_api(self, host_id):
        try:
            vnc_node = self.tf_client.read_node_by_hostname(host_id)

            node = {'name': host_id,
                    'ports': []}
            for port_ref in vnc_node.get_ports():
                port = self.tf_client.get_port(uuid=port_ref['uuid'])
                pi = port.get_physical_interface_back_refs()
                if pi:
                    node['ports'].append({'name': port.fq_name[-1],
                                          'port_name': pi[0]['to'][-1],
                                          'switch_name': pi[0]['to'][-2]})
            if len(node['ports']) == 0:
                LOG.error("Node %s has no port connected to physical interface"
                          % host_id)
                raise InvalidNodeError
            return node
        except (AttributeError, TypeError) as err:
            LOG.error("Error during collecting node details from API. "
                      "For node %s data in API are incomplete" % host_id)
            LOG.exception(err)
            raise InvalidNodeError

    @property
    def _file_loaded(self):
        return self.topology is not None


class NodeNotFoundError(Exception):
    pass


class InvalidNodeError(Exception):
    pass
