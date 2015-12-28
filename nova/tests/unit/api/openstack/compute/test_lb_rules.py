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

from nova.api.openstack.compute import lb_rules as lb_rules_v2
from nova.loadbalancer.manager import LoadBalancer
from nova import exception
from nova import test
from nova.tests.unit.api.openstack import fakes

import mock
import webob

FAKE_LB_RULES = {
    'lb_rule 1': {
        'id': 1,
        'type': 'host',
        'value': 'compute1.*',
        'allow': False,
    },
    'lb_rule 2': {
        'id': 2,
        'type': 'ha',
        'value': 'ha1',
        'allow': True,
    },
}


def fake_get_all_lb_rules_sorted_list(context=None, inactive=False,
                                      filters=None, sort_key='id',
                                      sort_dir='asc', limit=None, marker=None):
    if marker in ['99999']:
        raise exception.MarkerNotFound(marker)

    def reject_min(db_attr, filter_attr):
        return (filter_attr in filters and
                int(lb_rule[db_attr]) < int(filters[filter_attr]))

    filters = filters or {}
    res = []
    for (lb_rule_name, lb_rule) in FAKE_LB_RULES.items():
        res.append(lb_rule)

    res = sorted(res, key=lambda item: item[sort_key])
    output = []
    marker_found = True if marker is None else False
    for lb_rule in res:
        if not marker_found and marker == lb_rule['id']:
            marker_found = True
        elif marker_found:
            if limit is None or len(output) < int(limit):
                output.append(lb_rule)
    return output


def fake_lb_rule_get_all(self, context=None):
    return [lb_rule for _, lb_rule in FAKE_LB_RULES.iteritems()]


def empty_get_all_lb_rules_sorted_list(context=None, inactive=False,
                                       filters=None, sort_key='id',
                                       sort_dir='asc', limit=None,
                                       marker=None):
    return []


def return_lb_rule_not_found(rule_id, ctxt=None):
    raise exception.LbRuleNotFound(lb_rule_id=rule_id)


class LbRulesControllerTestV2(test.TestCase):
    _prefix = "/v2/fake"
    Controller = lb_rules_v2.Controller
    fake_request = fakes.HTTPRequest
    _fake = "/fake"

    def setUp(self):
        super(LbRulesControllerTestV2, self).setUp()
        self.flags(osapi_compute_extension=[])
        fakes.stub_out_networking(self.stubs)
        fakes.stub_out_rate_limiting(self.stubs)
        self.stubs.Set(LoadBalancer, "lb_rule_get_all", fake_lb_rule_get_all)
        self.controller = self.Controller()

    def _check_response(self, controller_method, response, expected_code):
        self.assertEqual(expected_code, controller_method.wsgi_code)

    def test_get_lb_rule_list(self):
        request = self.fake_request.blank(self._prefix + '/loadbalancer/rules')
        lb_rule = self.controller.index(request)
        expected = {
            "lb_rules": [
                {
                    'id': 2,
                    'type': 'ha',
                    'value': 'ha1',
                    'allow': True,
                },
                {
                    'id': 1,
                    'type': 'host',
                    'value': 'compute1.*',
                    'allow': False,
                },
            ],
        }
        self.assertEqual(lb_rule, expected)

    @mock.patch('nova.loadbalancer.manager.LoadBalancer.lb_rule_create',
                return_value={"id": 3,
                              "type": u'ha',
                              "value": u'ha2',
                              "allow": False})
    def test_create_lb_rule(self, create_mocked):
        request = self.fake_request.blank(self._prefix + '/loadbalancer/rules')
        body = {
            "lb_rule":
                {
                    "id": 3,
                    "type": u'ha',
                    "value": u'ha2',
                    "allow": False
                }
            }
        request.method = 'POST'
        response = self.controller.create(request, body=body)
        print "RESPONSE: %s" % response
        lb_rule = response['lb_rule']
        self.assertEqual(body['lb_rule']['id'], lb_rule['id'])

    @mock.patch('nova.loadbalancer.manager.LoadBalancer.lb_rule_delete')
    def test_delete_lb_rule(self, delete_mocked):
        request = self.fake_request.blank(self._prefix +
                                          '/loadbalancer/rules/1')
        request.method = 'DELETE'
        response = self.controller.delete(request, '1')
        self._check_response(self.controller.delete, response, 204)
        delete_mocked.assert_called_once_with(mock.ANY, '1')

    @mock.patch('nova.loadbalancer.manager.LoadBalancer.lb_rule_delete',
                side_effect=webob.exc.HTTPNotFound())
    def test_delete_lb_rule_not_found(self, _delete_mocked):
        request = self.fake_request.blank(self._prefix +
                                          '/loadbalancer/rules/300')
        request.method = 'DELETE'
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.delete, request, '300')

