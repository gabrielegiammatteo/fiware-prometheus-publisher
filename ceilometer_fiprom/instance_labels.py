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
import os
import fcntl
import pickle

from ceilometer.openstack.common import log
from ceilometer_fiprom.util import FileConfiguration

LOG = log.getLogger(__name__)

UNKNOWN_VALUE = None
COMPLETE_LABEL = '_complete'

DEFAULT_INSTANCE_DIMENSIONS = {

    'instance':     UNKNOWN_VALUE,
    'instance_id':  UNKNOWN_VALUE,
    'user':         UNKNOWN_VALUE,
    'user_id':      UNKNOWN_VALUE,
    'tenant':       UNKNOWN_VALUE,
    'tenant_id':    UNKNOWN_VALUE,
    'tenant_group': UNKNOWN_VALUE,
    'image':        UNKNOWN_VALUE,
    'flavor':       UNKNOWN_VALUE,
    'host':         UNKNOWN_VALUE,
    'host_id':      UNKNOWN_VALUE,
    'vcpus':        UNKNOWN_VALUE,
    'ram':          UNKNOWN_VALUE,
    'disk':         UNKNOWN_VALUE,
    COMPLETE_LABEL: False  # specify whether all dta about the instance has been extracted
}


class NamesMapping(FileConfiguration):
    '''
    Since Ceilometer samples contains in most cases only the id of objects (user, tenant, host)
    we load an id-name mapping from a file and use it to add name label in the Prometheus metrics
    '''

    def _parse(self, content):
        self.names = {}

        for row in content.split('\n'):
            # prefer ":" if present as delimiter
            if (':' in row) or ('=' in row):
                delimter = ':|='
            else:
                delimter = '\ |,|\t'
            tokens = re.split(delimter, row, 1)
            if len(tokens) < 2:
                continue
            self.names[tokens[0].strip()] = tokens[1].strip()


class TenantGroupMapping(NamesMapping):
    '''
    Load the tenant group of each tenant from file
    '''
    pass


class InstanceLabelsCache(object):
    cache = {}
    __needs_dump = False

    def __init__(self, cache_file):
        self.cache_file = cache_file

        # load from file
        # a lock on the file is used to avoid multiple instance
        # of the publisher to read/write at the same time

        # TODO: Ideally, only one instance of the publisher should run because if we have multiple instances
        # the caches could be not synchronized. They should not cache on the same file, but since multiple
        # Ceilometer poller/agents uses the same pipeline.yaml, each process will start a new process of the
        # publisher.
        try:
            with open(self.cache_file, 'r+') as cf:
                fcntl.lockf(cf, fcntl.LOCK_EX)
                self.cache = pickle.load(cf)
                fcntl.lockf(cf, fcntl.LOCK_UN)
        except:
            pass

    def dump_to_file(self):
        LOG.debug("Dumping cache to file")

        with open(self.cache_file, 'w+') as cf:
            fcntl.lockf(cf, fcntl.LOCK_EX)

            # load the file if exist, otherwise init an empty dict
            try:
                file_cache = pickle.load(cf)
            except EOFError:
                file_cache = {}

            for id, v in self.cache.iteritems():
                if (id not in file_cache) or file_cache[id][COMPLETE_LABEL] is False:
                    file_cache[id] = v

            pickle.dump(file_cache, cf)
            fcntl.lockf(cf, fcntl.LOCK_UN)
        self.__needs_dump = False

    def needs_dump(self):
        ''' Returns whether it's time to dump the cache or not.'''

        if not os.path.isfile(self.cache_file):
            return True

        if self.__needs_dump:
            return True

        return False

    def update_names(self, names_dict):
        for k, v in self.cache.iteritems():
            if not v[COMPLETE_LABEL]:
                self.__update_cache(k, {
                    'user':   names_dict.get(v['user_id'],   UNKNOWN_VALUE),
                    'tenant': names_dict.get(v['tenant_id'], UNKNOWN_VALUE),
                    'host':   names_dict.get(v['host_id'],   UNKNOWN_VALUE)})
                self.__update_complete(v)

    def update_tenant_groups(self, groups_dict):
        for k, v in self.cache.iteritems():
            if not v[COMPLETE_LABEL]:
                self.__update_cache(k, {'tenant_group': \
                                            groups_dict.get[v['tenant_id']] if v['tenant_id'] in groups_dict else \
                                                groups_dict.get(v['tenant'], UNKNOWN_VALUE)})
                self.__update_complete(v)

    def add_instance_info(self, metric):
        ''' try to extract instnace info from a Sample. Not all samples contain them'''

        if not 'instance_id' in metric.labels:
            return

        instance_id = metric.labels['instance_id']
        if instance_id in self.cache and self.cache[instance_id]['_complete'] == True:
            # already in cache
            return

        self.cache[instance_id] = dict(DEFAULT_INSTANCE_DIMENSIONS) if instance_id not in self.cache else self.cache[
            instance_id]

        # first add data that we know is in all metrics
        self.__update_cache(instance_id, {
            'instance_id':  instance_id,
            'tenant_id':    metric.labels['tenant_id'],
            'user_id':      metric.labels['user_id']
        })

        s = metric.source
        self.__update_cache(instance_id, {
            'instance': s.resource_metadata.get('display_name', UNKNOWN_VALUE),
            'flavor':   s.resource_metadata['flavor']['name'] if 'flavor' in s.resource_metadata else UNKNOWN_VALUE,
            'image':    s.resource_metadata['image']['name'] if 'image' in s.resource_metadata else UNKNOWN_VALUE,
            'vcpus':    s.resource_metadata.get('vcpus', UNKNOWN_VALUE),
            'ram':      s.resource_metadata.get('memory_mb', UNKNOWN_VALUE),
            'disk':     s.resource_metadata.get('disk_gb', UNKNOWN_VALUE),
            'host_id':  s.resource_metadata.get('host', UNKNOWN_VALUE)
        })

        self.__update_complete(self.cache[instance_id])

    def __update_cache(self, instance_id, new_values, override=False):
        if override:
            self.cache[instance_id].update(new_values)
            self.__needs_dump = True
            return

        for k, v in new_values.iteritems():
            if k not in self.cache[instance_id] or self.cache[instance_id][k] == UNKNOWN_VALUE:
                if self.cache[instance_id][k] != v:
                    self.cache[instance_id][k] = v
                    self.__needs_dump = True

    def __update_complete(self, instance):
        complete = True
        for k, v in instance.iteritems():
            if v == UNKNOWN_VALUE:
                complete = False
                break
        if instance[COMPLETE_LABEL] != complete:
            instance[COMPLETE_LABEL] = complete
            self.__needs_dump = True

    def get(self, instance_id):
        return {k: v for k, v in self.cache.get(instance_id, {}).iteritems()
                if (k != COMPLETE_LABEL) and (v is not None)}
