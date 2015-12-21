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


from nova.api.openstack.compute.views import loadbalancer as balancer_views
from nova.api.openstack import wsgi
from nova.loadbalancer import manager
from nova import exception
from nova.objects.compute_node import ComputeNodeList
from webob import exc


class Controller(wsgi.Controller):
    """LoadBalancer controller for the OpenStack API."""

    _view_builder_class = balancer_views.ViewBuilder

    def index(self, req):
        """Return all flavors in brief."""
        nodes = self._get_nodes(req)
        return self._view_builder.index(req, nodes)

    def detail(self, req):
        """Return all flavors in detail."""
        limited_flavors = self._get_flavors(req)
        req.cache_db_flavors(limited_flavors)
        return self._view_builder.detail(req, limited_flavors)

    @wsgi.action('suspend_host')
    def suspend_host(self, req, body):
        context = req.environ['nova.context']
        host = body['suspend_host']['host']
        try:
            return manager.LoadBalancer().suspend_host(context, host)
        except (exception.ComputeHostNotFound,
                exception.ComputeHostWrongState,
                exception.ComputeHostForbiddenByRule) as e:
            raise exc.HTTPBadRequest(explanation=e.format_message())

    @wsgi.action('unsuspend_host')
    def unsuspend_host(self, req, body):
        context = req.environ['nova.context']
        print body
        hypervisor_hostname = body['unsuspend_host']['host']
        print "hostname: %s" % hypervisor_hostname
        node = ComputeNodeList.get_by_hypervisor(context, hypervisor_hostname)
        print node
        if node:
            try:
                return manager.LoadBalancer().unsuspend_host(context, node[0])
            except exception.ComputeHostWrongState as e:
                raise exc.HTTPBadRequest(explanation=e.format_message())
        else:
            msg = 'Requested node not found'
            raise exc.HTTPBadRequest(explanation=msg)

    def _get_nodes(self, req):
        """Helper function that returns a list of nodes dicts."""

        context = req.environ['nova.context']
        nodes = manager.LoadBalancer().get_nodes(context)
        return nodes


def create_resource():
    return wsgi.Resource(Controller())