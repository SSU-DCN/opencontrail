==============================
Installation and configuration
==============================

Installation of package depends on the environment you are running. The most general way to install package is::

    $ pip install \
      -c https://git.openstack.org/cgit/openstack/requirements/plain/upper-constraints.txt \
      -e git+https://git.openstack.org/openstack/networking-opencontrail#egg=networking-opencontrail

.. note:: If you only need a development environment, see :doc:`installation/playbooks`.

DevStack environment
--------------------

Installing networking-opencontrail as a DevStack plugin (see devstack README:
:doc:`devstack`) does not require any further configuration changes.

Manual configuration
--------------------

#. Assume you installed the plugin as described at the beginning of the chapter using ``pip``

#. Adjust ``/etc/neutron/neutron.conf`` to meet the example.

   * Ensure you have ``ml2`` core plugin enabled.
   * Add ``opencontrail-router`` to ``service_plugins`` list.
   * Change default ``network_scheduler_driver``.
     More description in :doc:`architecture/dhcp_scheduler`.

   Example:

   .. literalinclude:: samples/neutron.conf.sample
      :language: ini

#. Edit ``/etc/neutron/plugins/ml2/ml2_conf.ini`` file:

   * Add ``opencontrail`` to ``mechanism_drivers`` list in ``ml2`` section.

   After editing file should look similarly to this:

   .. literalinclude:: samples/ml2_conf.ini.sample
      :language: ini

#. Create a new file ``/etc/neutron/plugins/ml2/ml2_conf_opencontrail.ini``
   and write an IP and a port of the Tungsten Fabric REST API to meet the example:

   .. literalinclude:: samples/ml2_conf_opencontrail.ini.sample
      :language: ini
      :lines: 1-3

#. If you want to use integration with Device Manager, enable it in the same
   file (see :doc:`device_manager` for details) like:

   .. literalinclude:: samples/ml2_conf_opencontrail.ini.sample
      :language: ini
      :lines: 5-7

#. Make sure you include all config files in the Neutron server parameters::

    /usr/local/bin/neutron-server --config-file /etc/neutron/neutron.conf \
    --config-file /etc/neutron/plugins/ml2/ml2_conf.ini \
    --config-file /etc/neutron/plugins/ml2/ml2_conf_opencontrail.ini

#. Restart neutron-server


Manual configuration on a Kolla deployment
------------------------------------------

Installation the plugin on a Kolla deployment for a development version
does not much differ from manual installation.
There are only some minor differences like config file locations.

Assume that the Kolla was deployed using this guide: `kolla_quickstart`_.

.. _kolla_quickstart: https://docs.openstack.org/kolla-ansible/queens/user/quickstart.html

#. Install plugin into neutron_server docker container::

    docker exec -it neutron_server git clone https://opendev.org/x/networking-opencontrail.git /tmp/networking-opencontrail
    docker exec -u 0 -it neutron_server bash -c 'cd /tmp/networking-opencontrail; python setup.py install'

#. Edit section Default in ``/etc/kolla/neutron-server/neutron.conf``:

   .. literalinclude:: samples/neutron.conf.sample
      :language: ini

#. Edit section ml2 in ``/etc/kolla/neutron-server/ml2_conf.ini``:

   .. literalinclude:: samples/ml2_conf.ini.sample
      :language: ini

#. Add file ``/etc/kolla/neutron-server/ml2_conf_opencontrail.ini``:

   .. literalinclude:: samples/ml2_conf_opencontrail.ini.sample
      :language: ini
      :lines: 1-3

#. If you want to use an integration with Device Manager, enable it in the same
   file (see :doc:`device_manager` for details) like:

   .. literalinclude:: samples/ml2_conf_opencontrail.ini.sample
      :language: ini
      :lines: 5-7

#. Edit ``/etc/kolla/neutron-server/config.json``:

   #. Add ``--config-file /etc/neutron/ml2_conf_opencontrail.ini`` at the end of neutron-server command
   #. Add ``ml2_conf_opencontrail.ini`` to config files::

            "config_files": [
            {
                  "source": "/var/lib/kolla/config_files/ml2_conf_opencontrail.ini",
                  "dest": "/etc/neutron/ml2_conf_opencontrail.ini",
                  "owner": "neutron",
                  "perm": "0600"
            },

#. Restart neutron::

    docker restart neutron_server
