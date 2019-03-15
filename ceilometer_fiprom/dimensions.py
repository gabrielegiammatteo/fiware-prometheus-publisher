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
import time

import os
import pickle
import re


from ceilometer.openstack.common import log
LOG = log.getLogger(__name__)


class NamesMapping(object):

    def __init__(self, names_file):
        self._file = names_file
        self.__last_update = 0

    def needs_reload(self):

        if not os.path.isfile(self._file):
            return False

        if self.__last_update < os.stat(self._file).st_mtime:
            return True

    def get_from_file(self):

        res = {}

        with open(self._file, 'rb') as file:
            for row in file.read().split('\n'):
                tokens = re.split('\ |,|\t|:', row, 1)
                if len(tokens) < 2:
                    continue
                res[tokens[0]] = tokens[1]

        return res


class TenantGroupMapping(NamesMapping):
    pass

class CommonDimensionsCache(object):


    cache = {}

    _empty_dimensions = {
        'vm_id': 'unknown',
        'vm_name': 'unknown',
        'user_id': 'unknown',
        'tenant_id': 'unknown',
        'flavor': 'unknown',
        'image': 'unknown',
        'user_name': 'unknown',
        'tenant_name': 'unknown',
        'tenant_group': 'unknown',
        'host': 'unknown',
        'unit': 'unknown'
    }



    def __init__(self, cache_file):
        self.cache_file = cache_file

        try:
            with open(self.cache_file, 'r+') as cf:
                self.cache = pickle.load(cf)
        except:
            pass

    def dump_to_file(self):
        LOG.debug("Dumping cahce to file")
        with open(self.cache_file, 'w') as cf:
            pickle.dump(self.cache, cf)

    def needs_dump(self):
        if not os.path.isfile(self.cache_file):
            return True

        if time.time() > os.stat(self.cache_file).st_mtime + 60 * 15: # every 15 minutes
            return True

        return False

    def update_names(self, names_dict):
        for k, v in self.cache.iteritems():
            v['user_name'] = names_dict.get(v['user_id'], 'unknown')
            v['tenant_name'] = names_dict.get(v['tenant_id'], 'unknown')


    def update_tenant_groups(self, groups_dict):
        for k, v in self.cache.iteritems():
            v['tenant_group'] = groups_dict.get(v['tenant_id'], 'unknown')


    def add(self, metric):
        s = metric.source

        if s.name.startswith('network') or s.name.startswith('disk'):
            # do not consider network.* and disk.* metrics to get common metadata
            # because they have different metadata than the others
            return

        if s.resource_id in self.cache:
            # already in cache
            return

        self.cache[s.resource_id] = dict(self._empty_dimensions)
        self.cache[s.resource_id].update({
            'vm_id': s.resource_id,
            'vm_name': s.resource_metadata['display_name'],
            'user_id': s.user_id,
            'tenant_id': s.project_id,
            'flavor': s.resource_metadata['flavor']['name'],
            'image': s.resource_metadata['image']['name'],
            'host': s.resource_metadata['host']
        })


    def get(self, instance_id):
        return self.cache.get(instance_id, self._empty_dimensions)





