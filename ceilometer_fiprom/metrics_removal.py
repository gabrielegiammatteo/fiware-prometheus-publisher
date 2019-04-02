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
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class StaleMetricsRemoval(object):
    '''
    By design the PushGateway never remove metrics, so metrics of deleted instances will remain in the PushGateway and
    will be returned when Prometheus scrape it. The only way to delete metrics in the PushGateway is to make a
    DELETE request to the PushGateway with the grouping keys of metrics that must be deleted in the URL.

    This class keeps track of the grouping keys published to the PushGateway and the timestamp of the last time it has
    been published. When the garbage_collector() method is invoked, for each grouping keys in memory the last time
    it has been published is checked and if it is expired
    '''


    def __init__(self, publisher, stale_time_seconds):
        self.publisher = publisher
        self.stale_time = stale_time_seconds
        self.__init_cache()

    def __init_cache(self):
        self.grouping_keys_cache = {}
        self.push_time_cache = {}
        # TODO: load initial values from the pushgateway push_time_seconds metrics
        pass

    def cache_post(self, grouping_key):
        k = hash(frozenset(grouping_key.items()))
        self.push_time_cache[k] = time.time()
        self.grouping_keys_cache[k] = grouping_key
        LOG.debug('Grouping keys inserted in cache: %s with hash %s', grouping_key, k)

    def garbage_collector(self):
        # TODO: not optimized implementation. If timestamp would be sorted, we could iterate only until the first
        # not expired item

        now = time.time()

        for k in self.push_time_cache.keys():
            v = self.push_time_cache[k]
            if v < now - self.stale_time:
                LOG.info('Removing grouping keys %s because not published since %s seconds', self.grouping_keys_cache[k], now - v)
                self._remove_metrics(self.grouping_keys_cache[k])
                self.push_time_cache.pop(k)
                self.grouping_keys_cache.pop(k)

    def _remove_metrics(self, grouping_key):
        url = self.publisher.pushgateway + '/' + '/'.join(['{0}/{1}'.format(k, v) for k, v in grouping_key.iteritems()])
        self.publisher._do_delete(url)



