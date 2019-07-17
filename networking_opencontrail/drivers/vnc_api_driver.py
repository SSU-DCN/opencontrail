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

import functools

from oslo_config import cfg
from oslo_log import log as logging

from vnc_api import vnc_api

LOG = logging.getLogger(__name__)


class VncApiClient(object):
    DEFAULT_GLOBAL_CONF = "default-global-system-config"
    ID_PERMS = vnc_api.IdPermsType(
        creator="networking-opencontrail", enable=True)

    class vnc_connect(object):
        """Connect to VNC API on first use method that needs connection"""

        def __init__(self, func):
            functools.update_wrapper(self, func)
            self._func = func

        def __call__(self, obj, *args, **kwargs):
            if not obj.vnc_lib:
                obj.vnc_lib = vnc_api.VncApi(
                    api_server_host=cfg.CONF.APISERVER.api_server_ip,
                    api_server_port=cfg.CONF.APISERVER.api_server_port,
                    api_server_use_ssl=cfg.CONF.APISERVER.use_ssl,
                    apicertfile=cfg.CONF.APISERVER.certfile,
                    apikeyfile=cfg.CONF.APISERVER.keyfile,
                    apicafile=cfg.CONF.APISERVER.cafile,
                    apiinsecure=cfg.CONF.APISERVER.insecure,
                    auth_type=cfg.CONF.auth_strategy,
                    auth_host=cfg.CONF.keystone_authtoken.auth_host,
                    auth_port=cfg.CONF.keystone_authtoken.auth_port,
                    auth_protocol=cfg.CONF.keystone_authtoken.auth_protocol,
                    tenant_name=cfg.CONF.keystone_authtoken.admin_tenant_name,
                    kscertfile=cfg.CONF.keystone_authtoken.certfile,
                    kskeyfile=cfg.CONF.keystone_authtoken.keyfile,
                    ksinsecure=cfg.CONF.keystone_authtoken.insecure)
            return self._func(obj, *args, **kwargs)

        def __get__(self, instance, instancetype):
            return functools.partial(self.__call__, instance)

    def __init__(self):
        self.vnc_lib = None

    def read_pi_from_switch(self, switch_name, pi_name):
        pi_fq_name = [self.DEFAULT_GLOBAL_CONF, switch_name, pi_name]
        return self.get_physical_interface(fq_name=pi_fq_name)

    def get_project(self, uuid=None, fq_name=None):
        return self._get_object("project", uuid=uuid, fq_name=fq_name)

    def get_physical_interface(self, uuid=None, fq_name=None):
        return self._get_object("physical_interface",
                                uuid=uuid, fq_name=fq_name)

    def get_virtual_network(self, uuid=None, fq_name=None):
        return self._get_object("virtual_network", uuid=uuid, fq_name=fq_name)

    def get_virtual_machine_interface(self, uuid=None, fq_name=None):
        return self._get_object(
            "virtual_machine_interface", uuid=uuid, fq_name=fq_name)

    def get_virtual_port_group(self, uuid=None, fq_name=None):
        return self._get_object("virtual_port_group",
                                uuid=uuid, fq_name=fq_name)

    @vnc_connect
    def create_virtual_machine_interface(self, vmi):
        try:
            self.vnc_lib.virtual_machine_interface_create(vmi)
        except vnc_api.RefsExistError:
            LOG.debug("VMI %s already exists in VNC", vmi.name)

    @vnc_connect
    def delete_virtual_machine_interface(self, fq_name):
        try:
            self.vnc_lib.virtual_machine_interface_delete(fq_name=fq_name)
        except vnc_api.NoIdError:
            LOG.warning("Cannot delete VMI %s: not exists" % fq_name)

    @vnc_connect
    def update_virtual_port_group(self, vpg):
        try:
            self.vnc_lib.virtual_port_group_update(vpg)
        except vnc_api.NoIdError:
            LOG.warning("Cannot update VPG %s: not exists" % vpg.name)

    @vnc_connect
    def _get_object(self, obj_name, uuid=None, fq_name=None):
        func_name = "%s_read" % obj_name
        read_obj = getattr(self.vnc_lib, func_name)
        try:
            return read_obj(id=uuid, fq_name=fq_name)
        except vnc_api.NoIdError:
            return None

    @classmethod
    def make_virtual_machine_interface(cls, name, network, properties,
                                       bindings, project):
        vmi = vnc_api.VirtualMachineInterface(name=name, parent_obj=project)
        vmi.set_id_perms(cls.ID_PERMS)
        vmi.add_virtual_network(network)
        vmi.set_virtual_machine_interface_properties(properties)
        vmi.set_virtual_machine_interface_bindings(bindings)
        return vmi

    @staticmethod
    def make_vmi_properties_with_vlan_tag(vlan_tag):
        vmi_properties = vnc_api.VirtualMachineInterfacePropertiesType(
            sub_interface_vlan_tag=vlan_tag)
        return vmi_properties

    @staticmethod
    def make_key_value_pairs(pairs):
        kv_list = [vnc_api.KeyValuePair(key=k, value=v) for k, v in pairs]
        return vnc_api.KeyValuePairs(kv_list)
