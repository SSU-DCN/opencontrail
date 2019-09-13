# Copyright (c) 2019 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import ddt

from vnc_api import vnc_api

from networking_opencontrail.tests.base import IntegrationTestCase


@ddt.ddt
class TestDeviceManager(IntegrationTestCase):
    """Integration tests for Device Manager integration.

    Those tests expect to enable DM integration in environment.
    """

    LAST_VLAN_ID = 100
    FABRIC = {'qfx-test-1': ['xe-0/0/0'],
              'qfx-test-2': ['xe-0/0/0',
                             'xe-1/1/1']}
    TOPOLOGY = {'compute-node': {'port-1':
                                 ('qfx-test-1', 'xe-0/0/0')},
                'compute-2': {'port-1':
                              ('qfx-test-2', 'xe-0/0/0'),
                              'port-2':
                              ('qfx-test-2', 'xe-1/1/1')}}

    @classmethod
    def setUpClass(cls):
        super(TestDeviceManager, cls).setUpClass()
        cls._vnc_api = vnc_api.VncApi(api_server_host=cls.contrail_ip)
        cls._cleanup_topology_queue = []
        cls._cleanup_fabric_queue = []

        try:
            cls._make_fake_fabric()
            cls._make_fake_topology()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        super(TestDeviceManager, cls).tearDownClass()
        cls._cleanup()

    def setUp(self):
        super(TestDeviceManager, self).setUp()

        self.test_network, self.vlan_id = self._make_vlan_network()

    def test_create_vlan_port_on_node_creates_dm_bindings(self):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        self.q_create_port(**port)
        vmi_name = self._make_vmi_name(self.test_network, 'compute-node')

        vmi_uuid = self._find_vmi(vmi_name)
        self._assert_dm_vmi(vmi_uuid,
                            self.test_network['network']['id'],
                            self.vlan_id,
                            [('qfx-test-1', 'xe-0/0/0')])

    def test_create_two_ports_on_two_nodes(self):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        self.q_create_port(**port)

        port.update({'device_id': 'vm-2',
                     'binding:host_id': 'compute-2'})
        self.q_create_port(**port)

        vpg_uuids = set()
        expected_bindings = [('compute-node', [('qfx-test-1', 'xe-0/0/0')]),
                             ('compute-2', [('qfx-test-2', 'xe-0/0/0'),
                                            ('qfx-test-2', 'xe-1/1/1')])]
        for compute_name, physical_interfaces in expected_bindings:
            vmi_name = self._make_vmi_name(self.test_network, compute_name)
            vmi_uuid = self._find_vmi(vmi_name)
            self._assert_dm_vmi(vmi_uuid,
                                self.test_network['network']['id'],
                                self.vlan_id,
                                physical_interfaces)

            vmi = self.tf_get_resource('virtual-machine-interface', vmi_uuid)
            vpg_uuids.add(vmi['virtual_port_group_back_refs'][0]['uuid'])

        self.assertEqual(2, len(vpg_uuids))

    @ddt.data({'binding:host_id': 'ummanaged-node'},
              {'device_id': ''},
              {'device_owner': 'not-compute:fake'})
    def test_create_unmanaged_port_not_creates_dm_bindings(self, change):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        port.update(change)
        self.q_create_port(**port)

        vmi_name = self._make_vmi_name(self.test_network,
                                       port['binding:host_id'])
        vmi_uuid = self._find_vmi(vmi_name)
        self.assertIsNone(vmi_uuid)

    def test_create_port_in_not_vlan_network_not_creates_dm_bindings(self):
        net = {'name': 'test_notvlan_network',
               'admin_state_up': True,
               'provider:network_type': 'local'}
        network = self.q_create_network(**net)

        port = {'name': 'test_fabric_port',
                'network_id': network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        self.q_create_port(**port)
        vmi_name = self._make_vmi_name(network, 'compute-node')

        vmi_uuid = self._find_vmi(vmi_name)
        self.assertIsNone(vmi_uuid)

    def test_update_port_changes_node(self):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        q_port = self.q_create_port(**port)
        vmi_name = self._make_vmi_name(self.test_network, 'compute-node')

        vmi_uuid = self._find_vmi(vmi_name)
        self._assert_dm_vmi(vmi_uuid,
                            self.test_network['network']['id'],
                            self.vlan_id,
                            [('qfx-test-1', 'xe-0/0/0')])

        self.q_update_port(q_port, **{'binding:host_id': 'compute-2'})

        self.assertIsNone(self._find_vmi(vmi_name))
        vmi_name_2 = self._make_vmi_name(self.test_network, 'compute-2')
        vmi_uuid_2 = self._find_vmi(vmi_name_2)
        self._assert_dm_vmi(vmi_uuid_2,
                            self.test_network['network']['id'],
                            self.vlan_id,
                            [('qfx-test-2', 'xe-0/0/0'),
                             ('qfx-test-2', 'xe-1/1/1')])

    @ddt.data({'binding:host_id': 'unmanaged-node'},
              {'device_id': ''},
              {'device_owner': 'not-compute:fake'})
    def test_update_port_removes_bindings(self, change):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        q_port = self.q_create_port(**port)
        vmi_name = self._make_vmi_name(self.test_network, 'compute-node')

        vmi_uuid = self._find_vmi(vmi_name)
        self._assert_dm_vmi(vmi_uuid,
                            self.test_network['network']['id'],
                            self.vlan_id,
                            [('qfx-test-1', 'xe-0/0/0')])

        vmi = self.tf_get_resource('virtual-machine-interface', vmi_uuid)
        vpg_uuid = vmi['virtual_port_group_back_refs'][0]['uuid']

        self.q_update_port(q_port, **change)

        vmi_uuid = self._find_vmi(vmi_name)
        self.assertIsNone(vmi_uuid)
        self._assert_vpg_deleted_or_not_ref(vpg_uuid, vmi_uuid)

    def test_delete_last_port_removes_dm_bindings(self):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        port = self.q_create_port(**port)
        vmi_name = self._make_vmi_name(self.test_network, 'compute-node')
        vmi_uuid = self._find_vmi(vmi_name)
        self.assertIsNotNone(vmi_uuid)

        vmi = self.tf_get_resource('virtual-machine-interface', vmi_uuid)
        vpg_uuid = vmi['virtual_port_group_back_refs'][0]['uuid']

        self.q_delete_port(port)

        self.assertIsNone(self._find_vmi(vmi_name))
        self._assert_vpg_deleted_or_not_ref(vpg_uuid, vmi_uuid)

    def test_delete_port_when_other_exists_not_removes_dm_bindings(self):
        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        q_port = self.q_create_port(**port)

        port.update({'device_id': 'vm-2'})
        self.q_create_port(**port)

        vmi_name = self._make_vmi_name(self.test_network, 'compute-node')
        self.assertIsNotNone(self._find_vmi(vmi_name))

        self.q_delete_port(q_port)

        self.assertIsNotNone(self._find_vmi(vmi_name))

    def test_three_ports_on_node(self):
        """Create three ports in two networks for the same Node, remove two

        There should be only one VMI per network on node. After remove port,
        VPG should not have reference to it any more.
        """

        port = {'name': 'test_fabric_port',
                'network_id': self.test_network['network']['id'],
                'binding:host_id': 'compute-node',
                'device_id': 'vm-1',
                'device_owner': 'compute:fake-nova'}
        self.q_create_port(**port)

        port.update({'device_id': 'vm-2'})
        q_port_2 = self.q_create_port(**port)

        network_2, vlan_2 = self._make_vlan_network()
        port.update({'device_id': 'vm-3',
                     'network_id': network_2['network']['id']})
        q_port_3 = self.q_create_port(**port)

        vmi_uuids = []
        vpg_uuids = set()
        expected_bindings = [(self.test_network, self.vlan_id, 'compute-node'),
                             (network_2, vlan_2, 'compute-node')]
        for network, vlan_id, compute_name in expected_bindings:
            vmi_name = self._make_vmi_name(network, compute_name)
            vmi_uuid = self._find_vmi(vmi_name)
            self._assert_dm_vmi(vmi_uuid,
                                network['network']['id'],
                                vlan_id,
                                [('qfx-test-1', 'xe-0/0/0')])
            vmi_uuids.append(vmi_uuid)

            vmi = self.tf_get_resource('virtual-machine-interface', vmi_uuid)
            vpg_uuids.add(vmi['virtual_port_group_back_refs'][0]['uuid'])

        self.assertEqual(1, len(vpg_uuids))

        self.q_delete_port(q_port_2)
        self.q_delete_port(q_port_3)

        vpg = self.tf_get_resource('virtual-port-group', vpg_uuids.pop())
        self.assertTrue(self._check_vpg_contains_vmi_ref(vpg, vmi_uuids[0]))
        self.assertFalse(self._check_vpg_contains_vmi_ref(vpg, vmi_uuids[1]))

        ret = self.tf_request_resource('virtual-machine-interface',
                                       vmi_uuids[1])
        self.assertEqual(404, ret.status_code)

    def _find_vmi(self, vmi_name):
        vmis = self.tf_list_resource('virtual-machine-interface')
        return next((vmi['uuid'] for vmi in vmis
                     if vmi['fq_name'][-1] == vmi_name),
                    None)

    def _assert_vpg_deleted_or_not_ref(self, vpg_uuid, vmi_uuid):
        ret = self.tf_request_resource('virtual-port-group', vpg_uuid)
        if ret.status_code != 404:
            vpg = self.tf_get_resource('virtual-port-group', vpg_uuid)
            self.assertFalse(self._check_vpg_contains_vmi_ref(
                vpg, vmi_uuid))

    def _assert_dm_vmi(self, vmi_uuid, net_uuid, vlan, physical_interfaces):
        """Assert that VMI with bindings for DM is created properly.

            1. VMI uuid exists
            2. VMI is connected only to given network
            3. VMI has right VLAN tag
            4. VMI has reference to one VPG and this VPG has reference to it
            5. VPG is connected only to expected physical interfaces
        """

        self.assertIsNotNone(vmi_uuid)
        vmi = self.tf_get_resource('virtual-machine-interface', vmi_uuid)

        self.assertEqual(1, len(vmi.get('virtual_network_refs', [])))
        self.assertEqual(net_uuid, vmi['virtual_network_refs'][0]['uuid'])
        self.assertEqual(vlan,
                         vmi.get('virtual_machine_interface_properties', {})
                         .get('sub_interface_vlan_tag'))

        self.assertEqual(1, len(vmi.get('virtual_port_group_back_refs', [])))
        vpg_uuid = vmi['virtual_port_group_back_refs'][0]['uuid']
        vpg = self.tf_get_resource('virtual-port-group', vpg_uuid)
        self.assertTrue(self._check_vpg_contains_vmi_ref(vpg, vmi_uuid))

        pi_refs = {tuple(ref['to'][-2:])
                   for ref in vpg.get('physical_interface_refs', [])}
        self.assertEqual(set(physical_interfaces), pi_refs)

    def _check_vpg_contains_vmi_ref(self, vpg, vmi_uuid):
        vmi_refs = vpg.get('virtual_machine_interface_refs', [])
        for ref in vmi_refs:
            if ref['uuid'] == vmi_uuid:
                return True
        return False

    def _make_vlan_network(self):
        vlan_id = self.LAST_VLAN_ID = self.LAST_VLAN_ID + 1
        net = {'name': 'test_vlan_{}_network'.format(vlan_id),
               'admin_state_up': True,
               'provider:network_type': 'vlan',
               'provider:physical_network': 'vhost',
               'provider:segmentation_id': vlan_id}
        network = self.q_create_network(**net)
        return network, vlan_id

    @staticmethod
    def _make_vmi_name(vn_dict, host_id):
        return "_vlan_tag_for_vn_{}_compute_{}".format(
            vn_dict['network']['id'],
            host_id)

    @classmethod
    def _make_fake_fabric(cls):
        fabric = vnc_api.Fabric('fabric01')
        cls._fabric_uuid = cls._vnc_api.fabric_create(fabric)
        cls._vnc_api.fabric_read(id=cls._fabric_uuid)
        cls._cleanup_fabric_queue.append(('fabric', cls._fabric_uuid))

        for pr_name in cls.FABRIC:
            pr = vnc_api.PhysicalRouter(pr_name)
            pr.set_fabric(fabric)
            pr_uuid = cls._vnc_api.physical_router_create(pr)
            cls._cleanup_fabric_queue.append(('physical_router', pr_uuid))

            for pi_name in cls.FABRIC[pr_name]:
                pi = vnc_api.PhysicalInterface(name=pi_name, parent_obj=pr)
                pi_uuid = cls._vnc_api.physical_interface_create(pi)
                cls._cleanup_fabric_queue.append(
                    ('physical_interface', pi_uuid))

    @classmethod
    def _make_fake_topology(cls):
        for node_name in cls.TOPOLOGY:
            node = vnc_api.Node(node_name, node_hostname=node_name)
            node_uuid = cls._vnc_api.node_create(node)
            cls._cleanup_topology_queue.append(('node', node_uuid))

            for port_name, port_pi in cls.TOPOLOGY[node_name].items():
                ll_obj = vnc_api.LocalLinkConnection(switch_info=port_pi[0],
                                                     port_id=port_pi[1])
                bm_info = vnc_api.BaremetalPortInfo(
                    address='00-00-00-00-00-00',
                    local_link_connection=ll_obj)
                node_port = vnc_api.Port(port_name, node,
                                         bms_port_info=bm_info)
                port_uuid = cls._vnc_api.port_create(node_port)
                cls._cleanup_topology_queue.append(('port', port_uuid))

    @classmethod
    def _add_vpg_to_cleanup(cls):
        fabric = cls._vnc_api.fabric_read(id=cls._fabric_uuid)
        for vpg_ref in fabric.get_virtual_port_groups() or []:
            cls._cleanup_fabric_queue.append(
                ('virtual_port_group', vpg_ref['uuid']))

    @classmethod
    def _cleanup(cls):
        cls._add_vpg_to_cleanup()
        reraise = False

        for queue in [cls._cleanup_fabric_queue, cls._cleanup_topology_queue]:
            for resource, res_uuid in reversed(queue):
                try:
                    del_func = getattr(cls._vnc_api,
                                       "{}_delete".format(resource))
                    del_func(id=res_uuid)
                except Exception:
                    reraise = True

        if reraise:
            raise
