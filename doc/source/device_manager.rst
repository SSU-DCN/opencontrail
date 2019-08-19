===============================
Integration with Device Manager
===============================

Networking-opencontrail supports integration with Device Manager from
Tungsten Fabric. It allows to automatically configure VLAN tags and VXLAN on
switches connected to computes, when virtual machine is plugged into a VLAN
network.

Configuration
=============

Prerequisites
-------------

* Encapsulation priorities in vrouter should be set with ``VXLAN`` on the
  first place.
* Fabric (including discovering switches) should be onboarded and Device
  Manager should be allowed to manage them.

.. seealso::

    To see details about fabric configuration and onboarding, see Juniper
    documentation, e.g. `Fabric Management <fabric_doc_>`_.

    .. _fabric_doc: https://www.juniper.net/documentation/en_US/contrail5.0/topics/task/configuration/ems-capabilities-on-physical-network-elements.html#id-fabric-management

Enable integration
------------------

Configuration options are inside group ``DM_INTEGRATION`` in plugin config
file, typically in ``/etc/neutron/plugins/ml2/ml2_conf_opencontrail.ini``

There are two options:

* ``enabled`` is boolean and should be set to ``True`` to enable integration
  with Device Manager; default value is ``False``,
* ``topology`` is a place for path to file with details about computes and
  their physical connections. This is optional and when not set, topology
  is got from Tungsten Fabric API.

.. literalinclude:: samples/ml2_conf_opencontrail.ini.sample
   :language: ini
   :lines: 5-7

After changing configuration restart Open Stack service.

Describing topology
-------------------

As written above, topology includes list of compute hosts and their connections
to switches. Integration with Device Manager will be provided only for listed
computes and there will be no impact for other hosts. There are two ways to
describe topology.

**First** is to use a YAML file and
set paths to compute hosts in ``topology`` option. Each node represents one compute host.
It should contain unique name and a list of ports where compute is connected,
including names of a switch and port on it. Example file is below.

.. literalinclude:: samples/topology.yaml.sample
   :language: yaml

**Second** is to use Tungsten Fabric API. This way works by leaving
``topology`` setting empty and importing details about nodes into TF. Each ``node`` should
represent a single compute host and have refs to their ``ports``, which should
be connected to related ``physical interfaces``.

Changes in topology file require a plugin reload, but changes made using API are applied
immediately. At this moment, no changes have any impact on existing VM
connections.

.. important::

    In either case, the name of node must be the same as compute name used by
    Open Stack. Integration is only triggered when compute name matches to one
    of the nodes in topology.

Usage
=====

When a virtual machine on one of the managed computes is connected to a VLAN network,
the plugin creates an additional VMI in Tungsten Fabric API, which then triggers Device
Manager to configure VLAN tagging on all switch ports connected to this host
and related VXLAN. When no VM in a VLAN network runs on the compute,
the VLAN tagging should be removed for this host.

.. note::

    Plugin only creates and removes VMI in Tungsten Fabric. Any other actions,
    particularly pushing configuration to the switches is done by Device Manager,
    which is required to configure them properly. You can read more about what the plugin
    does on the page :doc:`architecture/dm_integration`.
