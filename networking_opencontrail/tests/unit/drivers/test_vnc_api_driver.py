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

from vnc_api import vnc_api

from networking_opencontrail.drivers import vnc_api_driver
from networking_opencontrail.tests import base


@ddt.ddt
class VncApiDriverTestCase(base.TestCase):
    @mock.patch("oslo_config.cfg.CONF",
                APISERVER=mock.MagicMock(topology=None))
    def setUp(self, config):
        super(VncApiDriverTestCase, self).setUp()
        self.vnc_api = mock.Mock()
        vnc_api_driver.vnc_api.VncApi = mock.Mock(return_value=self.vnc_api)

        self.driver = vnc_api_driver.VncApiClient()

    def test_make_virtual_machine_interface(self):
        project = self._get_fake_project()
        vn = self._get_fake_vn()
        properties = self._get_fake_vmi_properties()
        bindings = self._get_fake_vmi_bindings()

        vmi = self.driver.make_virtual_machine_interface(
            "vmi-1", vn, properties, bindings, project)

        self.assertIsInstance(vmi, vnc_api.VirtualMachineInterface)
        self.assertEqual(vmi.get_virtual_network_refs()[0]['uuid'], vn.uuid)
        self.assertEqual(len(vmi.get_virtual_network_refs()), 1)
        self.assertEqual(vmi.get_virtual_machine_interface_properties(),
                         properties)
        self.assertEqual(vmi.get_virtual_machine_interface_bindings(),
                         bindings)
        self.assertEqual(vmi.get_id_perms().get_creator(),
                         "networking-opencontrail")
        self.assertEqual(vmi.name, "vmi-1")
        self.assertEqual(vmi.get_parent_fq_name(), project.fq_name)

    def test_make_vmi_properties_with_vlan_tag(self):
        vlan_tag = 101

        properties = self.driver.make_vmi_properties_with_vlan_tag(vlan_tag)

        self.assertIsInstance(properties,
                              vnc_api.VirtualMachineInterfacePropertiesType)
        self.assertEqual(properties.get_sub_interface_vlan_tag(), vlan_tag)

    def test_make_key_value_pairs(self):
        data = [("key-1", "val-1"), ("key-2", "val-2")]

        kv_pairs = self.driver.make_key_value_pairs(data)

        self.assertIsInstance(kv_pairs, vnc_api.KeyValuePairs)
        dict_translation = {
            "KeyValuePairs": {
                "key_value_pair": [{"key": "key-1", "value": "val-1"},
                                   {"key": "key-2", "value": "val-2"}]}}
        self.assertEqual(kv_pairs.exportDict(), dict_translation)

    @mock.patch("oslo_config.cfg.CONF")
    def test_read_pi_from_switch(self, cfg):
        self.driver.read_pi_from_switch("switch-1", "pi-1")

        self.vnc_api.physical_interface_read.assert_called_with(
            fq_name=["default-global-system-config", "switch-1", "pi-1"],
            id=None)

    @mock.patch("oslo_config.cfg.CONF")
    def test_create_virtual_machine_interface(self, cfg):
        vmi = mock.Mock()

        self.driver.create_virtual_machine_interface(vmi)

        self.vnc_api.virtual_machine_interface_create.assert_called_with(vmi)

    @mock.patch("oslo_config.cfg.CONF")
    def test_create_virtual_machine_interface_no_raise_on_refsexist(self, cfg):
        vmi = mock.Mock()
        self.vnc_api.virtual_machine_interface_create = mock.Mock(
            side_effect=vnc_api.RefsExistError)

        self.driver.create_virtual_machine_interface(vmi)

        self.vnc_api.virtual_machine_interface_create.assert_called_with(vmi)

    @mock.patch("oslo_config.cfg.CONF")
    def test_delete_virtual_machine_interface(self, cfg):
        self.driver.delete_virtual_machine_interface(["name"])

        self.vnc_api.virtual_machine_interface_delete.assert_called_with(
            fq_name=["name"])

    @mock.patch("oslo_config.cfg.CONF")
    def test_delete_virtual_machine_interface_no_raise_on_noiderror(self, cfg):
        self.vnc_api.virtual_machine_interface_delete = mock.Mock(
            side_effect=vnc_api.NoIdError("id"))

        self.driver.delete_virtual_machine_interface(["name-1"])

        self.vnc_api.virtual_machine_interface_delete.assert_called_with(
            fq_name=["name-1"])

    @mock.patch("oslo_config.cfg.CONF")
    def test_update_virtual_port_group(self, cfg):
        vpg = mock.Mock()
        self.driver.update_virtual_port_group(vpg)

        self.vnc_api.virtual_port_group_update.assert_called_with(vpg)

    @mock.patch("oslo_config.cfg.CONF")
    def test_update_virtual_port_group_no_raise_on_noiderror(self, cfg):
        vpg = mock.Mock()
        self.vnc_api.virtual_port_group_update = mock.Mock(
            side_effect=vnc_api.NoIdError("id"))

        self.driver.update_virtual_port_group(vpg)

        self.vnc_api.virtual_port_group_update.assert_called_with(vpg)

    @ddt.data("physical_interface",
              "virtual_network",
              "virtual_machine_interface",
              "project",
              "virtual_port_group")
    @mock.patch("oslo_config.cfg.CONF")
    def test_get_objects_from_vnc_api(self, object_name, cfg):
        get_func = "get_%s" % object_name
        vnc_get_func_name = "%s_read" % object_name
        vnc_read = mock.Mock(return_value=mock.Mock())
        self.vnc_api.configure_mock(**{vnc_get_func_name: vnc_read})

        obj = getattr(self.driver, get_func)(uuid="uuid-1", fq_name=["name-1"])

        self.assertEqual(obj, vnc_read.return_value)
        vnc_read.assert_called_with(id="uuid-1", fq_name=["name-1"])

    @ddt.data("physical_interface",
              "virtual_network",
              "virtual_machine_interface",
              "project",
              "virtual_port_group")
    @mock.patch("oslo_config.cfg.CONF")
    def test_get_objects_from_vnc_api_when_obj_not_exists(self,
                                                          object_name, cfg):
        get_func = "get_%s" % object_name
        vnc_get_func_name = "%s_read" % object_name
        vnc_read = mock.Mock(side_effect=vnc_api.NoIdError("id"))
        self.vnc_api.configure_mock(**{vnc_get_func_name: vnc_read})

        obj = getattr(self.driver, get_func)(uuid="uuid-1", fq_name=["name-1"])

        self.assertIsNone(obj)
        vnc_read.assert_called_with(id="uuid-1", fq_name=["name-1"])

    @mock.patch("oslo_config.cfg.CONF")
    def test_vnc_connect_decorator(self, config):
        args = mock.Mock()
        kwargs = mock.Mock()

        class Test(object):
            def __init__(self):
                self.vnc_lib = None

            @self.driver.vnc_connect
            def test(self, arg, kwarg):
                return (arg, kwarg)

        test_obj = Test()
        value1 = test_obj.test(args, kwarg=kwargs)
        value2 = test_obj.test(args, kwarg=kwargs)

        vnc_api_driver.vnc_api.VncApi.assert_called_once()
        self.assertEqual(test_obj.vnc_lib, self.vnc_api)
        self.assertEqual(value1, (args, kwargs))
        self.assertEqual(value2, (args, kwargs))

    def _get_fake_project(self):
        return mock.Mock(uuid="proj-1", fq_name=["project-1"])

    def _get_fake_vn(self):
        return mock.Mock(uuid="vn-1", fq_name=["net-1"])

    def _get_fake_vmi_properties(self):
        return mock.Mock()

    def _get_fake_vmi_bindings(self):
        return mock.Mock()
