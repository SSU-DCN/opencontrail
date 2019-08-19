==================================
Device Manager integration details
==================================

Plugin can trigger Device Manager to automatically manage underlay: VLAN tags on
switch interfaces and VXLAN. Using this, compute hosts can be dynamically
connected to VLANs used by virtual machines that run on them.

Networking-opencontrail triggers DM by creating a *virtual
machine interface* in Tungsten Fabric for each affected VM, that contains references
to the right virtual network, expected VLAN tag and bindings for physical interfaces, that
need to be configured. Any other actions, like pushing configuration, is done
by Tungsten Fabric/Device Manager.

Prerequisites in TF
===================

Plugin expects that at least fabric is onboarded. That means, switches and
their interfaces that will be used during integration are represented in TF API
as ``physical router`` and ``physical interfaces`` and physical router has
reference to the ``fabric`` object.

When topology is provided from TF API, it is also expected that any managed
compute hosts and all of its ports are represented by the ``node`` and ``port`` objects.
It is important that each node needs to have the same name as used by Open Stack and
any port that is connected to switch needs to have reference to the corresponding physical
interface object. Ports without PI refs will be ignored.

When topology is provided from file, representation of compute hosts/ports
as ``node``/``port`` objects is not necessary, but still every switch interface
has to be a ``physical interface`` in TF and each of the node names has to be
the same as those used by Open Stack.

To use VXLAN encapsulation vRouter must be configured to use it as a default.

.. seealso::

    How to configure plugin for DM integration is described on page
    :doc:`../device_manager`. Onboarding fabric is out-of-scope of this
    document.

Integration flow
================

When DM integration is enabled, on startup the plugin tries to load topology from a file
if path to it was given.

Then, plugin calls methods for integration during ``update_port_postcommit``
in ML2 framework. First, if the compute host, network or VM id has changed,
plugin tries to delete old DM-related VMI. Next it checks if current
port is connected to a VM on a host that exists in the topology (in topology file or
when file is not given, in TF API) and a VLAN virtual network.

When DM should be informed about this VM, plugin checks if related VMI not
exists yet. If not, creates a new VMI in TF that has:

* reference to virtual network (created previous by networking-opencontrail),
* ``sub_interface_vlan_tag`` property with VLAN tag value,
* name created from template ``_vlan_tag_for_vm_<vm-uuid>_vn_<vn-uuid>``,
* ``profile bindings`` dictionary that contains list of affected switches,
  their interfaces, fabric name and VPG name (if VPG object exists).

Fabric name for any switch is read from API. For selecting a VPG, plugin check
if there exists any auto-created VPG that has a reference to every physical interface
which is connected to this compute. If it does not exist, VPG name will not be listed in binding
and it should be created automatically by TF.

On ``delete_port_postcommit`` in ML2 framework, plugin deletes DM-related
VMI if it exists.

.. note::

    VPG is a ``virtual port group`` object in TF that groups physical
    interfaces. This provide support for both LAG and multihoming. More about
    them you can read in `Juniper VPG documentation <vpg_doc_>`_.

    .. _vpg_doc: https://www.juniper.net/documentation/en_US/contrail5.1/topics/concept/contrail-virtual-port-groups.html

Expected result
===============

After creating VMI, the plugin has no more work left to do. After a while it is expected
that related switches will be configured to have VLAN tagging on specific ports
and VXLAN. Each VLAN tag is selected by plugin (from Open Stack VLAN virtual
network), whereas VXLAN id is managed by Tungsten Fabric (typically this is
value of ``virtual_network_network_id`` property from virtual network in TF).

Expected switch configuration looks like (on QFX)::

    admin@qfx> show configuration interfaces xe-0/0/1 | display inheritance no-comments
    flexible-vlan-tagging;
    mtu 9192;
    encapsulation extended-vlan-bridge;
    unit 251 {
        vlan-id 251;
    }

    admin@qfx> show configuration vlans | display inheritance no-comments
    bd-8 {
        vlan-id none;
        interface xe-0/0/1.251;
        vxlan {
            vni 8;
        }
    }

.. note::

    This is only an example of possible configuration. Config is being managed by
    Device Manager and results depend on DM settings and possibilities.

.. tip::

    If right VMI is created in API but after a while there occurs no config changes
    on device, check Device Manager logs.


Known limitations
=================

There is a few not supported cases:

* when network change VLAN tag, existing VMI are not updated,
* when topology file is changed, plugin needs to be restarted to reload
  topology.
* any topology change doesn't affect existing VMI.
