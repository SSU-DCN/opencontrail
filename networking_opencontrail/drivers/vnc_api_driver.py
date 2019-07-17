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

from oslo_config import cfg
from oslo_log import log as logging

from networking_opencontrail.drivers.drv_opencontrail import \
    OpenContrailDrivers
from vnc_api import vnc_api

LOG = logging.getLogger(__name__)


class VncApiClient(OpenContrailDrivers):
    def __init__(self):
        super(VncApiClient, self).__init__()
        self._vnc_lib = vnc_api.VncApi(
            api_server_host=cfg.CONF.APISERVER.api_server_ip,
            api_server_port=cfg.CONF.APISERVER.api_server_port,
            api_server_use_ssl=cfg.CONF.APISERVER.use_ssl,
            apicertfile=cfg.CONF.APISERVER.certfile,
            apikeyfile=cfg.CONF.APISERVER.keyfile,
            apicafile=cfg.CONF.APISERVER.cafile,
            apiinsecure=cfg.CONF.APISERVER.insecure,
            auth_type=cfg.CONF.auth_strategy,
            tenant_name=cfg.CONF.keystone_authtoken.admin_tenant_name,
            kscertfile=cfg.CONF.keystone_authtoken.certfile,
            kskeyfile=cfg.CONF.keystone_authtoken.keyfile,
            kscafile=cfg.CONF.keystone_authtoken.cafile,
            ksinsecure=cfg.CONF.keystone_authtoken.insecure,
            auth_token_url=self._keystone_url)
