# Copyright (c) 2015 Servionica, LLC
# All Rights Reserved.
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

from nova import db
from nova import exception
from nova import objects
from nova import utils as nova_utils
from nova.objects.compute_node import ComputeNodeList
from nova.objects.instance import InstanceList
from nova.loadbalancer.underload.base import Base
from nova.loadbalancer.balancer.minimizeSD import MinimizeSD
from nova.loadbalancer import utils
from nova.compute import rpcapi as compute_api
from oslo_log import log as logging
from oslo_config import cfg

lb_opts = [
    cfg.FloatOpt('threshold_cpu',
                 default=0.05,
                 help='CPU Underload Threshold'),
    cfg.FloatOpt('threshold_memory',
                 default=0.05,
                 help='Memory Underload Threshold'),
    cfg.FloatOpt('unsuspend_cpu',
                 default=0.40,
                 help='CPU Unsuspend Threshold'),
    cfg.FloatOpt('unsuspend_memory',
                 default=0.40,
                 help='CPU Unsuspend Threshold')
]


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opts(lb_opts, 'loadbalancer_mean_underload')


class MeanUnderload(Base):

    def __init__(self):
        self.minimizeSD = MinimizeSD()

    def indicate(self, context, **kwargs):
        extra = kwargs.get('extra_info')
        cpu_th = CONF.loadbalancer_mean_underload.threshold_cpu
        memory_th = CONF.loadbalancer_mean_underload.threshold_memory
        compute_nodes = utils.get_compute_node_stats(context, use_mean=True)
        if len(compute_nodes) <= 1:
            self._indicate_unsuspend_host(context, extra_info=extra)
            return

        instances = []
        for node in compute_nodes:
            node_instances = db.get_instances_stat(context,
                                                   node['hypervisor_hostname'])
            instances.extend(node_instances)
        compute_stats = utils.fill_compute_stats(instances, compute_nodes)
        host_loads = utils.calculate_host_loads(compute_nodes, compute_stats)
        for node in host_loads:
            memory = host_loads[node]['mem']
            cpu = host_loads[node]['cpu']
            if (cpu < cpu_th) or (memory < memory_th):
                if self.suspend_host(context, node):
                    return
        self._indicate_unsuspend_host(context, extra_info=extra)

    def suspend_host(self, context, node):
        compute_node = ComputeNodeList.get_by_hypervisor(context, node)
        if not compute_node:
            raise exception.ComputeHostNotFound(host=node)
        LOG.debug('underload is needed')
        db.compute_node_update(context, compute_node[0]['id'],
                               {'suspend_state': 'suspending'})
        if self.minimizeSD.migrate_all_vms_from_host(context, node):
            return True
        else:
            db.compute_node_update(context, compute_node[0]['id'],
                                   {'suspend_state': 'active'})

    def _indicate_unsuspend_host(self, context, extra_info=None):
        cpu_mean = extra_info.get('cpu_mean')
        ram_mean = extra_info.get('ram_mean')
        unsuspend_cpu = CONF.loadbalancer_mean_underload.unsuspend_cpu
        unsuspend_ram = CONF.loadbalancer_mean_underload.unsuspend_memory
        if cpu_mean > unsuspend_cpu or ram_mean > unsuspend_ram:
            compute_nodes = db.compute_node_get_all(context,
                                                    read_suspended='only')
            for node in compute_nodes:
                self.unsuspend_host(context, node)
                return

    def unsuspend_host(self, context, node):
        mac_to_wake = node['mac_to_wake']
        nova_utils.execute('ether-wake', mac_to_wake, run_as_root=True)
        db.compute_node_update(context, node['id'],
                               {'suspend_state': 'active'})
        return True

    def _host_is_empty(self, context, host):
        alive_instances = InstanceList.get_by_filters(
            context,
            {'host': host, 'vm_state': 'active', 'deleted': False})
        shutdown_instances = InstanceList.get_by_filters(
            context,
            {'host': host, 'vm_state': 'stopped', 'deleted': False})
        if not alive_instances and not shutdown_instances:
            return True
        return False

    def check_is_all_vms_migrated(self, context):
        suspended_nodes = utils.get_compute_node_stats(
            context,
            read_suspended='suspending')
        for node in suspended_nodes:
            LOG.debug('Suspending host found: %s' % node)
            active_migrations = objects.migration.MigrationList\
                .get_in_progress_by_host_and_node(context,
                                                  node['hypervisor_hostname'],
                                                  node['hypervisor_hostname'])
            if active_migrations:
                LOG.debug('There is some migrations that are in active state')
                for migration in active_migrations:
                    if migration['status'] == 'finished':
                        self.minimizeSD.confirm_migration(
                            context,
                            migration['instace_uuid'])
                return
            else:
                if self._host_is_empty(context, node['hypervisor_hostname']):
                    mac = self.compute_rpc.prepare_host_for_suspending(
                        context, node['hypervisor_hostname'])
                    db.compute_node_update(context, node['compute_id'],
                                           {'mac_to_wake': mac})
                    self.compute_rpc.suspend_host(context,
                                                  node['hypervisor_hostname'])
                    db.compute_node_update(context, node['compute_id'],
                                           {'suspend_state': 'suspended'})
                else:
                    if not self.minimizeSD.migrate_all_vms_from_host(
                            context,
                            node['hypervisor_hostname']):
                        db.compute_node_update(context, node['compute_id'],
                                               {'suspend_state':
                                                'active'})
