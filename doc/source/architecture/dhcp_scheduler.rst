========================================
Not scheduling DHCP agent to TF networks
========================================

Both Neutron and Tungsten Fabric have their own DHCP service. When network
is managed by TF, only DHCP from TF works, but Neutron tries to
assign any network to DHCP agents. DHCP tries to create one port per
network and assign to it an IP from any subnet with enabled DHCP.
More details about agents can be found in `OpenStack documentation`_.

.. _OpenStack documentation: https://docs.openstack.org/neutron/latest/admin/config-dhcp-ha.html

Plugin handles it by checking if managed node exists in Tungsten Fabric and only binding port then,
thus suppresing natural binding process, and otherwise allowing openstack to proceed with default
port binding mechanisms.