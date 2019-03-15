#
# This publisher has been written to export Ceilometer metrics generated in
# the FIWARE node in Vicenza to Prometheus
#
# The Ceilometer version running in Vicenza is 2015.1.1 and it has not the
# official prometehus publisher added later in Ceilometer release.
#
# Copyright 2019, Engineering Ingegneria Informatica S.p.A.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import re
from ceilometer import sample

uuid4regex = re.compile('[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}', re.I)


class PromMetric(object):
    type = None
    name = None
    dimensions = {}
    value = None
    source = None


    def get_instance_id(self):
        if self.source.name.startswith('disk.device'):
            return self.dimensions['resource_id'][:36]

        if self.source.name.startswith('network'):
            try:
                return uuid4regex.search(self.dimensions['resource_id']).group(0)
            except Exception as ex:
                return self.dimensions['resource_id']


        return self.dimensions['resource_id']

    def __str__(self):
        dstring = ','.join(['{0}="{1}"'.format(k, v) for k, v in self.dimensions.iteritems()])
        return '[%s{%s} %s]' % (self.name, dstring, self.value)

    def __eq__(self, o):
        return self.name == o.name and self.dimensions == o.dimensions


def get_prom_metric(s):
    m = PromMetric()

    m.name = 'os_{0}'.format(s.name.replace('.','_'))
    m.value = s.volume

    # set the correct metric type
    if s.type == sample.TYPE_CUMULATIVE:
        m.type = "counter"
    elif s.type == sample.TYPE_GAUGE:
        m.type = "gauge"


    dimensions = {}
    dimensions['resource_id'] = s.resource_id
    dimensions['unit'] = s.unit

    m.dimensions = dimensions
    m.source = s

    return m