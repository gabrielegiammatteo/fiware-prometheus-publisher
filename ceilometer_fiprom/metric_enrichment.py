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

import os
import pickle
import re

from ceilometer.openstack.common import log
from ceilometer_fiprom.util import FileConfiguration

LOG = log.getLogger(__name__)


class LabelEnricher(object):
    pass

    def enrichLabels(self, metric):
        raise NotImplemented('Must be implemented')

    def updateCache(self, metric):
        raise NotImplemented('Must be implemented')


class NamesEnricher(LabelEnricher, FileConfiguration):

    def _parse(self, content):
        self.names = {}

        if not content:
            return

        for row in content.split('\n'):
            if row.startswith('#'):
                continue

            # prefer ":" if present as delimiter
            if (':' in row) or ('=' in row):
                delimter = ':|='
            else:
                delimter = '\ |,|\t'
            tokens = re.split(delimter, row, 1)
            if len(tokens) < 2:
                continue
            self.names[tokens[0].strip()] = tokens[1].strip()

    def enrichLabels(self, metric):
        if 'user_id' in metric.labels:
            metric.add_label('user', self.names.get(metric.labels['user_id'], None))

        if 'tenant_id' in metric.labels:
            metric.add_label('tenant', self.names.get(metric.labels['tenant_id'], None))

        if 'host_id' in metric.labels:
            metric.add_label('host', self.names.get(metric.labels['host_id'], None))

    def updateCache(self, metric):
        pass

    def needs_save(self):
        return False


class TenantGroupEnricher(NamesEnricher):

    def enrichLabels(self, metric):
        if 'tenant_id' in metric.labels:
            if metric.labels['tenant_id'] in self.names:
                metric.add_label('tenant_group', self.names.get(metric.labels['tenant_id'], None))
                return

        if 'tenant' in metric.labels:
            metric.add_label('tenant_group', self.names.get(metric.labels['tenant'], None))


class InstanceEnricher(LabelEnricher, FileConfiguration):
    cache = {}
    __needs_dump = False

    def _parse(self, content):
        if content:
            self.cache = pickle.loads(content)
        else:
            self.cache = {}

    def needs_reload(self):
        return False

    def save(self):
        LOG.debug("Dumping cache to file")

        with open(self._file, 'w') as cf:
            pickle.dump(self.cache, cf)

        self.__needs_dump = False

    def needs_save(self):
        ''' Returns whether it's time to dump the cache or not.'''

        if not os.path.isfile(self._file):
            return True

        if self.__needs_dump:
            return True

        return False

    def enrichLabels(self, metric):
        if 'instance_id' in metric.labels and metric.labels['instance_id'] in self.cache:
            metric.update_labels(self.cache[metric.labels['instance_id']])

    def updateCache(self, metric):

        if not 'instance_id' in metric.labels:
            return

        cache_id = metric.labels['instance_id']
        cache = self.cache.get(cache_id, {})

        self.__update_cache(cache, {
            '__cache_id': cache_id,
            'tenant_id': metric.labels['tenant_id'],
        })

        s = metric.source
        if s.resource_metadata:
            self.__update_cache(cache, {
                'instance': s.resource_metadata.get('display_name', None),
                'flavor':   s.resource_metadata['flavor'].get('name', None) if 'flavor' in s.resource_metadata else None,
                'image':    s.resource_metadata['image'].get('name', None) if 'image' in s.resource_metadata else None,
                'vcpus':    s.resource_metadata.get('vcpus', None),
                'ram':      s.resource_metadata.get('memory_mb', None),
                'disk':     s.resource_metadata.get('disk_gb', None),
                'host_id':  s.resource_metadata.get('host', None)
            })

        self.cache[cache_id] = cache

    def __update_cache(self, cache, new_values, override=False):
        if override:
            cache.update(new_values)
            self.__needs_dump = True
            return

        for k, v in new_values.iteritems():
            if v is None:
                continue
            try:
                if cache[k] is None or cache[k] != v:
                    self.__replace_key(cache, k, v)
            except KeyError:
                self.__replace_key(cache, k, v)

    def __replace_key(self, cache, k, v):
        cache[k] = v
        self.__needs_dump = True
        LOG.debug('Key "%s" added to "%s"', k, cache.get('__cache_id', None))
