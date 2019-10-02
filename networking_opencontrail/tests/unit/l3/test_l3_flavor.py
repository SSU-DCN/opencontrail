# Copyright (c) 2017 OpenStack Foundation
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
import logging
import mock

from neutron.tests.unit.extensions import base as test_extensions_base
from neutron_lib import constants as q_const

from networking_opencontrail.l3.l3_flavor import TFL3ServiceProvider


class L3FlavorTestCases(test_extensions_base.ExtensionTestCase):
    """Main test cases for L3 flavor mechanism driver for OpenContrail."""

    @mock.patch("networking_opencontrail.l3.snat_synchronizer."
                "SnatSynchronizer")
    @mock.patch("networking_opencontrail.drivers.drv_opencontrail."
                "OpenContrailDrivers")
    def setUp(self, driver, synchronizer):
        super(L3FlavorTestCases, self).setUp()
        logging.disable(logging.CRITICAL)

        self.provider = TFL3ServiceProvider(mock.MagicMock())

    def tearDown(self):
        super(L3FlavorTestCases, self).tearDown()
        logging.disable(logging.NOTSET)

    @mock.patch("networking_opencontrail.l3.l3_flavor.l3_obj."
                "Router.get_object")
    @mock.patch("networking_opencontrail.l3.l3_flavor.directory")
    def test_validate_l3_flavor_not_in_flavors(
            self, directory, get_router):
        router_id, router = self._get_router_test()
        context = self.get_mock_network_operation_context()

        flavor_plugin = self.mock_directory(directory)
        flavor_id = "123"

        self.assertFalse(
            self.provider._validate_l3_flavor(context, router_id, flavor_id))
        get_router.assert_not_called()
        flavor_plugin.get_flavor_next_provider.assert_called_with(
            context, flavor_id)

    @mock.patch("networking_opencontrail.l3.l3_flavor.l3_obj."
                "Router.get_object")
    @mock.patch("networking_opencontrail.l3.l3_flavor.directory")
    def test_validate_l3_flavor_in_flavors(
            self, directory, get_router):
        router_id, router = self._get_router_test()
        context = self.get_mock_network_operation_context()

        flavor_plugin = self.mock_directory(
            directory,
            provider="networking_opencontrail.l3.l3_flavor."
            "TFL3ServiceProvider")
        flavor_id = router.flavor_id

        self.assertTrue(
            self.provider._validate_l3_flavor(context, router_id, flavor_id))
        get_router.assert_not_called()
        flavor_plugin.get_flavor_next_provider.assert_called_with(
            context, flavor_id)

    @mock.patch("networking_opencontrail.l3.l3_flavor.l3_obj."
                "Router.get_object")
    @mock.patch("networking_opencontrail.l3.l3_flavor.directory")
    def test_validate_l3_flavor_in_flavors_without_id_provided(
            self, directory, get_router):
        router_id, router = self._get_router_test()
        get_router.return_value = router
        context = self.get_mock_network_operation_context()

        flavor_plugin = self.mock_directory(
            directory,
            provider="networking_opencontrail.l3.l3_flavor."
            "TFL3ServiceProvider")
        flavor_id = router.flavor_id

        self.assertTrue(
            self.provider._validate_l3_flavor(context, router_id))
        get_router.assert_called_with(context, id=router_id)
        flavor_plugin.get_flavor_next_provider.assert_called_with(
            context, flavor_id)

    @mock.patch("networking_opencontrail.l3.l3_flavor.l3_obj."
                "Router.get_object")
    @mock.patch("networking_opencontrail.l3.l3_flavor.directory")
    def test_validate_l3_flavor_undefined_is_not_found(
            self, directory, get_router):
        router_id, router = self._get_router_test()
        get_router.return_value = router
        context = self.get_mock_network_operation_context()

        self.mock_directory(
            directory,
            provider="networking_opencontrail.l3.l3_flavor."
            "TFL3ServiceProvider")

        self.assertFalse(
            self.provider._validate_l3_flavor(
                context, router_id, q_const.ATTR_NOT_SPECIFIED))

    @mock.patch("networking_opencontrail.l3.l3_flavor.l3_obj."
                "Router.get_object")
    @mock.patch("networking_opencontrail.l3.l3_flavor.directory")
    def test_validate_l3_flavor_without_router_is_not_found(
            self, directory, get_router):
        context = self.get_mock_network_operation_context()

        self.assertFalse(
            self.provider._validate_l3_flavor(context, None))

    def mock_directory(self, directory, provider=None):
        flavor_provider = {'driver': provider}
        flavor_plugin = mock.MagicMock()
        flavor_plugin.get_flavor_next_provider.return_value = [flavor_provider]

        directory.get_plugin.return_value = flavor_plugin

        return flavor_plugin

    @staticmethod
    def _get_router_test():
        router_id = "234237d4-1e7f-11e5-9bd7-080027328c3a"
        router = mock.MagicMock()
        router.name = 'router1'
        router.admin_state_up = True,
        router.tenant_id = router_id,
        router.project_id = router_id,
        router.external_gateway_info = None
        router.flavor_id = '1452df5e-dea5-11e9-9e0c-68071588b84b'

        return router_id, router

    @staticmethod
    def get_mock_network_operation_context():
        context = mock.Mock()

        return context
