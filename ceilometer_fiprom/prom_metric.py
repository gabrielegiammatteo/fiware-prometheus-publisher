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


# matches the id of resources (in uuid4 format)
uuid4regex = re.compile('[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}', re.I)


class PromMetric(object):

    def __init__(self, sample):
        self.source = sample
        self.labels = {}

    def add_label(self, key, value):
        self.labels[key] = value

    def get_instance_id(self):

        if 'instance_id' in self.labels:
            return self.labels['instance_id']

        if self.source.name.startswith('disk.device'):
            return self.labels['resource_id'][:36]

        if self.source.name.startswith('network'):
            try:
                return uuid4regex.search(self.labels['resource_id']).group(0)
            except Exception as ex:
                return self.labels['resource_id']

        return self.labels['resource_id']

    def update_labels(self, nlabels, override=False):
        if override:
            self.labels.update(nlabels)
            return

        for k, v in nlabels.iteritems():
            if k not in self.labels:
                self.labels[k] = v

    def __str__(self):
        dstring = ','.join(['{0}="{1}"'.format(k, v) for k, v in self.labels.iteritems()])
        return '[%s{%s} %s]' % (self.name, dstring, self.value)

    def __eq__(self, o):
        return self.name == o.name and self.labels == o.labels


def get_prom_metric(s):
    m = PromMetric(s)

    m.name = 'os_{0}'.format(s.name.replace('.', '_'))
    m.value = s.volume

    # set the correct metric type
    if s.type == sample.TYPE_CUMULATIVE:
        m.type = "counter"
    elif s.type == sample.TYPE_GAUGE:
        m.type = "gauge"

    m.add_label('resource_id', s.resource_id)
    m.add_label('unit', s.unit)
    m.add_label('instance_id', m.get_instance_id())
    m.add_label('user_id', s.user_id)

    if hasattr(s, 'project_id'):
        m.add_label('tenant_id', s.project_id)

    return m
