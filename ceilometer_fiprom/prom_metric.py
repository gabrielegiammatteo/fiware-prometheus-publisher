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
import yaml
import fnmatch

from ceilometer import sample
from ceilometer.openstack.common import log
from ceilometer_fiprom.util import FileConfiguration

LOG = log.getLogger(__name__)

# matches the id of resources (in uuid4 format)
uuid4regex = re.compile('[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}', re.I)


class PromMetric(object):

    def __init__(self, sample):
        self.source = sample
        self.labels = {}

    def add_label(self, key, value, ignore_none = True):
        if not ignore_none or (value is not None):
            self.labels[key] = value

    def update_labels(self, nlabels, override=False, ignore_none=True):
        if override:
            self.labels.update(nlabels)
            return

        for k, v in nlabels.iteritems():
            if k not in self.labels:
                self.add_label(k, v, ignore_none=ignore_none)

    def __eq__(self, o):
        return self.name == o.name and self.labels == o.labels


class SampleConverter(FileConfiguration):

    def _parse(self, content):
        if content:
            self.conf = yaml.load(content, Loader=yaml.SafeLoader)
        else:
            self.conf = {'enabled': [], 'labels': {}}

    def __is_enabled(self, name):
        for r in self.conf['enabled']:
            if fnmatch.fnmatch(name, r):
                return True
        return False

    def _load_rules(self, name):
        res = {}
        for r in self.conf['labels']:
            if fnmatch.fnmatch(name, r.keys()[0]):
                for d in r[r.keys()[0]]:
                    res.update(d)
        return res

    def get_prom_metric(self, s):

        m = PromMetric(s)

        if not self.__is_enabled(s.name):
            LOG.info('Dropping sample "%s" because not enabled', s.name)
            return None

        # set the correct metric type
        if s.type == sample.TYPE_CUMULATIVE:
            m.type = "counter"
        elif s.type == sample.TYPE_GAUGE:
            m.type = "gauge"
        else:
            LOG.warning('Dropping sample "%s" because type is not supported: %s', s.name, s.type)
            return None

        label_specs = self._load_rules(s.name)

        for k,v in label_specs.iteritems():

            globals = s.as_dict()
            globals.update({'uuid4regex': uuid4regex})
            globals.update(m.labels)

            try:
                if v is not None:
                    value = eval(v, globals)
                    m.add_label(k, value)
            except Exception as ex:
                LOG.warning('Error creating label "%s" for metric "%s". %s: %s',
                            k, m.labels.get('__name', None), ex.__class__.__name__, ex.message)

        m.name = m.labels['__name']
        m.value = m.labels['__value']
        return m
