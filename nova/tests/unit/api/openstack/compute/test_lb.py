# Copyright 2015 Servionica LLC
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


from nova.api.openstack.compute import loadbalancer as lb_v2
from nova.loadbalancer.manager import LoadBalancer
from nova.objects.compute_node import ComputeNodeList
from nova import exception
from nova import test
from nova.tests.unit.api.openstack import fakes

import mock
import webob

FAKE_LB_HOSTS = {
    "node 1": {
        "hypervisor_hostname": "compute1.students.dev",
        "cpu_used_percent": 14.0,
        "ram_total": 2048,
        "ram_used": 1024,
        "ram_used_percent": 50.0,
        "suspend_state": "active",
        "mac_to_wake": "00:00:00:00:00:00",
        "vcpus": 4
    },
    "node 2": {
        "hypervisor_hostname": "compute2.students.dev",
        "cpu_used_percent": 23.00,
        "ram_total": 4096,
        "ram_used": 1024,
        "ram_used_percent": 25.0,
        "suspend_state": "active",
        "mac_to_wake": "00:00:00:00:00:00",
        "vcpus": 8
    }
}


def fake_get_nodes():
    return [host for _, host in FAKE_LB_HOSTS.iteritems()]


class LbControllerTestV2(test.TestCase):
    """Test of the OpenStack API /loadbalancer application controller
    """
    _prefix = "/v2/fake"
    Controller = lb_v2.Controller
    fake_request = fakes.HTTPRequest
    _fake = "/fake"

    def setUp(self):
        super(LbControllerTestV2, self).setUp()
        self.flags(osapi_compute_extension=[])
        fakes.stub_out_networking(self.stubs)
        fakes.stub_out_rate_limiting(self.stubs)
        self.stubs.Set(LoadBalancer, "get_nodes", fake_get_nodes)
        self.controller = self.Controller()

    @mock.patch('nova.loadbalancer.manager.LoadBalancer.get_nodes',
                return_value=[{
                              'memory_used': 1024,
                              'cpu_used_percent': 20.0,
                              'hypervisor_hostname': 'compute1.students.dev',
                              'compute_id': 1,
                              'vcpus': 4,
                              'suspend_state': 'active',
                              'memory_total': 2048,
                              'mac_to_wake': '00:00:00:00:00:00'
                              },
                              {
                              'memory_used': 1024,
                              'cpu_used_percent': 20.0,
                              'hypervisor_hostname': 'compute2.students.dev',
                              'compute_id': 2,
                              'vcpus': 8,
                              'suspend_state': 'active',
                              'memory_total': 4096,
                              'mac_to_wake': '00:00:00:00:00:00'
                              },
                              ])
    def test_get_nodes(self, get_nodes_mocked):
        request = self.fake_request.blank(self._prefix + '/loadbalancer')
        request.method = 'GET'
        host_list = self.controller.index(request)
        expected = {"compute_nodes": [{
                    "hypervisor_hostname": "compute1.students.dev",
                    "cpu_used_percent": '20.00',
                    "ram_total": 2048,
                    "ram_used": 1024,
                    "ram_used_percent": '50.00',
                    "suspend_state": "active",
                    "mac_to_wake": "00:00:00:00:00:00",
                    "vcpus": 4},
                    {
                    "hypervisor_hostname": "compute2.students.dev",
                    "cpu_used_percent": '20.00',
                    "ram_total": 4096,
                    "ram_used": 1024,
                    "ram_used_percent": '25.00',
                    "suspend_state": "active",
                    "mac_to_wake": "00:00:00:00:00:00",
                    "vcpus": 8
                    }]}
        self.assertEqual(host_list, expected)

    @mock.patch('nova.loadbalancer.manager.LoadBalancer.suspend_host',
                return_value=True)
    def test_suspend_host(self, suspend_mocked):
        request = self.fake_request.blank(self._prefix +
                                          '/loadbalancer/action')
        request.method = 'POST'
        body = {"suspend_host": {"host": "compute1"}}
        response = self.controller.suspend_host(request, body)
        self.assertEqual(True, response)

    @mock.patch('nova.objects.compute_node.ComputeNodeList.get_by_hypervisor',
                return_value=[{'mac_to_wake': '00:00:00:00:00:00'}])
    @mock.patch('nova.loadbalancer.manager.LoadBalancer.unsuspend_host',
                return_value=True)
    def test_unsuspend_host(self, get_by_hp_mocked, unsuspend_mocked):
        request = self.fake_request.blank(self._prefix +
                                          '/loadbalancer/action')
        request.method = 'POST'
        body = {"unsuspend_host": {"host": "compute1"}}
        response = self.controller.unsuspend_host(request, body)
        self.assertEqual(True, response)

    @mock.patch('nova.objects.compute_node.ComputeNodeList.get_by_hypervisor',
                return_value=[{'mac_to_wake': '00:00:00:00:00:00'}])
    @mock.patch('nova.loadbalancer.manager.LoadBalancer.unsuspend_host',
                side_effect=exception.ComputeHostWrongState())
    def test_unsuspend_host_wrong_state(self, get_by_hp_mocked,
                                        _unsuspend_mocked):
        request = self.fake_request.blank(self._prefix +
                                          '/loadbalancer/action')
        request.method = 'POST'
        body = {"unsuspend_host": {"host": "compute1"}}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.unsuspend_host,
                          request, body)

    @mock.patch('nova.objects.compute_node.ComputeNodeList.get_by_hypervisor',
                return_value=[])
    def test_unsuspend_host_not_found(self, _get_by_hp_mocked):
        request = self.fake_request.blank(self._prefix +
                                          '/loadbalancer/action')
        request.method = 'POST'
        body = {"unsuspend_host": {"host": "zzz"}}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.unsuspend_host,
                          request, body)
