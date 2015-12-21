# Copyright (c) 2011 OpenStack Foundation
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

from oslo_config import cfg

from nova.objects.migration import MigrationList
from nova.scheduler import filters

opts = [
    cfg.IntOpt('max_migrations',
               default=10,
               help='Max numbers of migrations per node.')
]

CONF = cfg.CONF
CONF.register_opts(opts, 'loadbalancer')


class MaxMigrationsFilter(filters.BaseHostFilter):
    def host_passes(self, host_state, filter_properties):
        request_spec = filter_properties.get('request_spec')
        instance_properties = request_spec.get('instance_properties')
        source_host = instance_properties.get('host')
        context = filter_properties['context']
        dest_host = host_state.hypervisor_hostname
        if source_host:
            source_migrations = MigrationList.get_in_progress_by_host_and_node(
                context, source_host, source_host)
            if len(source_migrations) > CONF.loadbalancer.max_migrations:
                return False
        dest_migrations = MigrationList.get_in_progress_by_host_and_node(
            context, dest_host, dest_host)
        if len(dest_migrations) > CONF.loadbalancer.max_migrations:
            return False
        return True