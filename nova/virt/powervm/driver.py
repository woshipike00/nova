# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 IBM
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

import os
import time

from nova.compute import task_states
from nova.compute import vm_states

from nova import context as nova_context

from nova.image import glance

from nova.openstack.common import cfg
from nova.openstack.common import log as logging

from nova.virt import driver
from nova.virt.powervm import operator


LOG = logging.getLogger(__name__)

powervm_opts = [
    cfg.StrOpt('powervm_mgr_type',
               default='ivm',
               help='PowerVM manager type (ivm, hmc)'),
    cfg.StrOpt('powervm_mgr',
               default=None,
               help='PowerVM manager host or ip'),
    cfg.StrOpt('powervm_mgr_user',
               default=None,
               help='PowerVM manager user name'),
    cfg.StrOpt('powervm_mgr_passwd',
               default=None,
               help='PowerVM manager user password'),
    cfg.StrOpt('powervm_img_remote_path',
               default=None,
               help='PowerVM image remote path'),
    cfg.StrOpt('powervm_img_local_path',
               default=None,
               help='Local directory to download glance images to'),
    ]

CONF = cfg.CONF
CONF.register_opts(powervm_opts)


class PowerVMDriver(driver.ComputeDriver):

    """PowerVM Implementation of Compute Driver."""

    def __init__(self, virtapi):
        super(PowerVMDriver, self).__init__(virtapi)
        self._powervm = operator.PowerVMOperator()

    @property
    def host_state(self):
        pass

    def init_host(self, host):
        """Initialize anything that is necessary for the driver to function,
        including catching up with currently running VM's on the given host."""
        pass

    def get_info(self, instance):
        """Get the current status of an instance."""
        return self._powervm.get_info(instance['name'])

    def get_num_instances(self):
        return len(self.list_instances())

    def instance_exists(self, instance_name):
        return self._powervm.instance_exists(instance_name)

    def list_instances(self):
        return self._powervm.list_instances()

    def get_host_stats(self, refresh=False):
        """Return currently known host stats."""
        return self._powervm.get_host_stats(refresh=refresh)

    def plug_vifs(self, instance, network_info):
        pass

    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=None, block_device_info=None):
        """Create a new instance/VM/domain on powerVM."""
        self._powervm.spawn(context, instance, image_meta['id'])

    def destroy(self, instance, network_info, block_device_info=None,
                destroy_disks=True):
        """Destroy (shutdown and delete) the specified instance."""
        self._powervm.destroy(instance['name'], destroy_disks)

    def reboot(self, instance, network_info, reboot_type,
               block_device_info=None):
        """Reboot the specified instance.

        :param instance: Instance object as returned by DB layer.
        :param network_info:
           :py:meth:`~nova.network.manager.NetworkManager.get_instance_nw_info`
        :param reboot_type: Either a HARD or SOFT reboot
        """
        pass

    def get_host_ip_addr(self):
        """
        Retrieves the IP address of the dom0
        """
        pass

    def snapshot(self, context, instance, image_id):
        """Snapshots the specified instance.

        :param context: security context
        :param instance: Instance object as returned by DB layer.
        :param image_id: Reference to a pre-created image that will
                         hold the snapshot.
        """
        snapshot_start = time.time()

        # get current image info
        glance_service, old_image_id = glance.get_remote_image_service(
                context, instance['image_ref'])
        image_meta = glance_service.show(context, old_image_id)
        img_props = image_meta['properties']

        # build updated snapshot metadata
        snapshot_meta = glance_service.show(context, image_id)
        new_snapshot_meta = {'is_public': False,
                             'name': snapshot_meta['name'],
                             'status': 'active',
                             'properties': {'image_location': 'snapshot',
                                            'image_state': 'available',
                                            'owner_id': instance['project_id']
                                           },
                             'disk_format': image_meta['disk_format'],
                             'container_format': image_meta['container_format']
                            }

        if 'architecture' in image_meta['properties']:
            arch = image_meta['properties']['architecture']
            new_snapshot_meta['properties']['architecture'] = arch

        # disk capture and glance upload
        self._powervm.capture_image(context, instance, image_id,
                                    new_snapshot_meta)

        snapshot_time = time.time() - snapshot_start
        inst_name = instance['name']
        LOG.info(_("%(inst_name)s captured in %(snapshot_time)s seconds") %
                    locals())

    def pause(self, instance):
        """Pause the specified instance."""
        pass

    def unpause(self, instance):
        """Unpause paused VM instance."""
        pass

    def suspend(self, instance):
        """suspend the specified instance."""
        pass

    def resume(self, instance, network_info, block_device_info=None):
        """resume the specified instance."""
        pass

    def power_off(self, instance):
        """Power off the specified instance."""
        self._powervm.power_off(instance['name'])

    def power_on(self, instance):
        """Power on the specified instance."""
        self._powervm.power_on(instance['name'])

    def get_available_resource(self, nodename):
        """Retrieve resource info."""
        return self._powervm.get_available_resource()

    def host_power_action(self, host, action):
        """Reboots, shuts down or powers up the host."""
        pass

    def legacy_nwinfo(self):
        """
        Indicate if the driver requires the legacy network_info format.
        """
        return False

    def manage_image_cache(self, context, all_instances):
        """
        Manage the driver's local image cache.

        Some drivers chose to cache images for instances on disk. This method
        is an opportunity to do management of that cache which isn't directly
        related to other calls into the driver. The prime example is to clean
        the cache and remove images which are no longer of interest.
        """
        pass
