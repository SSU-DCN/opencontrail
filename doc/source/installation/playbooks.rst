=====================
Setup development VMs
=====================

Repository contains Ansible playbooks to automate creating development
environment. They are designed to setup at least two nodes. The first node
contains OpenStack with keystone, neutron, horizon, etc.
It has also networking-opencontrail plugin as neutron ML2 plugin
and service plugin for L3 driver. A second node contains nightly-build
contrail node with simple devstack as compute node.
Any number of nodes may be added as additional compute nodes.
Connectivity with those additional nodes bases on OpenVSwitch.

Playbooks deploy OpenStack in master version and OpenContrail in one of the latest nightly build.

Overview of deployment architecture:

.. figure:: deployment_architecture.png
    :width: 100%
    :align: center
    :alt: Diagram of deployment architecture

Step by step instruction is presented below.


*************
Initial steps
*************

Before you run playbooks perform the following steps:

**1. Prepare machines for Contrail and OpenStack nodes.**

Let's assume there are three hosts:

+-----------+--------------+--------------------------+------------+-------------+----------------------------------------+
| Node      | OS           | Recommended requirements | Public IP  | Internal IP | Notes                                  |
+===========+==============+==========================+============+=============+========================================+
| openstack | Ubuntu 16.04 | RAM: 8 GB                | 10.100.0.3 | 192.168.0.3 | devstack (controller node)             |
+-----------+--------------+--------------------------+------------+-------------+----------------------------------------+
| contrail  | CentOS 7.5   | RAM: 16 GB               | 10.100.0.2 | 192.168.0.2 | opencontrail + devstack (compute node) |
+-----------+--------------+--------------------------+------------+-------------+----------------------------------------+
| compute   | CentOS 7.5   | RAM: 8 GB                | 10.100.0.4 | 192.168.0.4 | devstack, OVS-only compute             |
+-----------+--------------+--------------------------+------------+-------------+----------------------------------------+

**2. Make sure you have key-based SSH access to prepared nodes**

.. code-block:: console

    $ ssh 10.100.0.2
    $ ssh 10.100.0.3
    $ ssh 10.100.0.4

**3. Install Ansible on your host**

It is required to install Ansible in version 2.5 or higher.

.. code-block:: console

    $ sudo add-apt-repository ppa:ansible/ansible
    $ sudo apt update
    $ sudo apt install python-netaddr ansible


*******************
Configure playbooks
*******************

Configuration require editing few files before running any playbook.

**1. Define nodes by specifying SSH names or IP of machines in playbooks/hosts**

Set contrail node, openstack node and all other compute nodes ``ansible_host``
to public IP of your machines. Then for compute nodes set ``local_ip`` to
it's internal IP address.

.. code-block:: text

    controller ansible_host=10.100.0.3 ansible_user=ubuntu

    # This host should be one from the compute host group.
    # Playbooks are not prepared to deploy tungsten fabric compute node separately.
    contrail_controller ansible_host=10.100.0.2 ansible_user=centos

    [compute]
    contrail_controller local_ip=192.168.0.2
    compute ansible_host=10.100.0.4 ansible_user=centos local_ip=192.168.0.4

The ``controller`` host is a machine to install OpenStack controller.
On ``contrail_controller``, the OpenConrail will be installed. All hosts
from the ``compute`` group will be a OpenStack computes.
Each compute is required to define ``local_ip`` variable with it's intenal ip
address.

**2. Change deployment variables in playbooks/group_vars/all.yml**

* ``contrail_ip`` and ``openstack_ip`` should be internal IP addresses.
* ``contrail_gateway`` should be gateway address of the contrail_ip.
* ``contrail_interface`` should be interface name that has bound contrail ip.

* ``openstack_branch`` should be set to ``master``
* ``install_networking_bgpvpn_plugin`` is a boolean value. If set true, it will
  install the neutron_bgpvpn plugin.

Next, there are variable useful if you want to enable integration with Device
Manager. Note that playbooks don't onboard fabric.

* ``dm_integration_enabled`` is boolean and when set true, DM integration will
  be enabled and encapsulation priority in vRouter set to required value.
* ``dm_topology_file`` is a place for path to file with topology on controller.
  When set, file `topology.yaml` from `playbooks/files` is copied to this
  location and plugin is configured to use them.

Last variables provide some useful options to configure VMs:

* ``change_password`` is a boolean value. If set true, the password on
  every machine (for user used by ansible) will be set to password given
  in ``instance_password`` variable.
* ``fix_docker_bip`` is a boolean value. If set true, the docker bridge CIDR
  will be set to value given in ``bip_cidr`` variable. This is for case, when
  default Docker bip can conflict with others.

.. code-block:: yaml

    # IP address for OpenConrail.
    contrail_ip: 192.168.0.2

    # Gateway address for OpenConrail.
    contrail_gateway: 192.168.0.1

    # Interface name for OpenConrail.
    contrail_interface: eth0


    # IP address for OpenStack VM.
    openstack_ip: 192.168.0.3

    # OpenStack branch used on VMs.
    openstack_branch: master

    # If true, then install networking_bgpvpn plugin with contrail driver
    install_networking_bgpvpn_plugin: false

    # If true, integration with Device Manager will be enabled and vRouter
    # encapsulation priorities will be set to 'VXLAN,MPLSoUDP,MPLSoGRE'.
    dm_integration_enabled: false

    # Optional path to file with topology for DM integration. When set and
    # DM integration enabled, topology.yaml file will be copied to this location
    dm_topology_file:

    # If true, password to the created instances for current ansible user
    # will be set to value of instance_password
    change_password: false
    instance_password: uberpass1

    # Set to true if you have conflict between docker network subnet and your local
    # network subnet. The docker bridge CIDR will be set to value of bip_cidr
    fix_docker_bip: false
    bip_cidr: 10.255.0.1/16

**********
Deployment
**********

Run playbooks
=============

.. note:: Before OpenStack deployment make sure playbooks are configured.

Execute ``playbooks/main.yml`` file.
Make sure you are in playbooks directory before executing the playbooks.
This will make Ansible to use local ``hosts`` file instead of system broad defined hosts.

.. code-block:: console

    $ cd playbooks
    $ ansible-playbook main.yml -i hosts

This playbooks can last 1 hour or more.

Please be patient while executing roles with ``stack.sh``.
Real time logs from these operations can be viewed on each host
by following command: ``less +F -R /opt/stack/logs/stack.sh.log``

*****
Usage
*****

Create availability groups
==========================

Currently all openvswitch based nodes (eg additional computes) should be put in separate
availability group.
If any additional hosts were provisioned,
in devstack UI should be manually created additional host aggregate using ``ovs`` availability zone,
and all compute hosts that are not ``contrail_controller`` node should be moved there.


Access web interface
====================

* http://10.100.0.3/ - devstack's horizon. Credentials: admin/admin

* https://10.100.0.2:8143/ - OpenContrail UI. Credentials: admin/contrail123 (domain can be empty or "default")

Create example VM
=================

After successful deployment, it could be possible to create sample Virtual Machine.

These commands should be ran on one of the nodes (both are connected to one neutron).
Assuming that contrail node has ``contrail-node.novalocal`` hostname (used in availability zone):

.. code-block:: console

    source ~/devstack/openrc admin demo
    openstack network create net
    openstack subnet create --network net --subnet-range 192.168.1.0/24 --dhcp subnet
    openstack security group rule create --ingress --protocol icmp default
    openstack security group rule create --ingress --protocol tcp default
    openstack server create --flavor cirros256 --image cirros-0.3.6-x86_64-uec --nic net-id=net \
      --availability-zone nova:contrail-node.novalocal instance

Created VM could be accessed by VNC (through horizon):

1. Go to horizon's list of VMs http://10.100.0.3/dashboard/project/instances/

2. Enter into the VM's console.

3. Login into. Default login/password is ``cirros/cubswin:)``
