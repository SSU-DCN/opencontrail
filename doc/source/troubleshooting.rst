===============
Troubleshooting
===============


#. ``BadRequest: Bad virtual_network request: physical network must be configured.``

   Please ensure that you create local or vlan network.

   The origin of the problem is in incompatibility of some network types between OpenStack and Tungsten Fabric.
   Tungsten Fabric's vnc_openstack module supports only vlan and local networks,
   because it needs physical network and segmentation id both to be provided (vlan) or both to be empty (local).

   Choosing these two networks that are compatible with Tungsten Fabric can be enforced by ml2 config.
   File /etc/neutron/plugins/ml2/ml2_conf.ini should contain similar line (for full example of ml2 configuration see :doc:`devstack`)::

    [ml2]
    tenant_network_types = local,vlan

#. **Fix problems with libvirt during devstack deployment**

   If there are any problems with libvirt, then the version of libvirt
   should be upgraded in devstack requirements. To do it, change
   version of `libvirt-python` in file `/opt/stack/requirements/upper-constraints.txt`

   The version of libvirt-python must be the same as, or newer than the
   version of the libvirt C library you're building against.

   Reference: https://www.redhat.com/archives/libvirt-users/2017-September/msg00003.html
