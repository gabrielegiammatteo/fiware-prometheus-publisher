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

from six.moves.urllib import parse as urlparse
from ceilometer.openstack.common import log
from ceilometer_fiprom.dimensions import CommonDimensionsCache, NamesMapping, TenantGroupMapping
from ceilometer_fiprom.prom_metric import get_prom_metric
from ceilometer_fiprom.util import HttpPublisher

LOG = log.getLogger(__name__)


class PrometheusPublisher(HttpPublisher):

    HEADERS = {'Content-type': 'plain/text'}


    def __init__(self, parsed_url):
        super(PrometheusPublisher, self).__init__(parsed_url)
        
        # Get cache and names files from URL parameters
        params = urlparse.parse_qs(parsed_url.query)
        self.cache_file = self._get_param(params, 'cache_file', '/tmp/fiprom_publisher_cache', str)
        self.names_file = self._get_param(params, 'names_file', '/tmp/fiprom_publisher_names', str)
        self.tenant_group_file = self._get_param(params, 'tenant_group_file', '/tmp/fiprom_publisher_tenant_group', str)
        max_parallel_requests = self._get_param(params, 'max_parallel_requests', 10, int)

        LOG.info('using cache_file at %s', self.cache_file)
        LOG.info('using names_file at %s', self.names_file)
        LOG.info('using tenant_group_file at %s', self.tenant_group_file)
        LOG.info('using max_parallel_requests: %d', max_parallel_requests)

        self.common_dimensions_cache = CommonDimensionsCache(self.cache_file)
        self.names_mapping = NamesMapping(self.names_file)
        self.tenant_group_mapping = TenantGroupMapping(self.tenant_group_file)


    def publish_samples(self, context, samples):

        if not samples:
            return

        LOG.debug('Got %d samples to publish', len(samples))

        # transform to Prometheus metrics
        metrics = [get_prom_metric(s) for s in samples]

        # search for common metadata to add in cache
        map(self.common_dimensions_cache.add, metrics)

        # update metric dimensions adding common metadata
        for m in metrics:
            m.dimensions.update(self.common_dimensions_cache.get(m.get_instance_id()))

        if(self.names_mapping.needs_reload()):
            self.common_dimensions_cache.update_names(self.names_mapping.get_from_file())

        if(self.tenant_group_mapping.needs_reload()):
            self.common_dimensions_cache.update_tenant_groups(self.tenant_group_mapping.get_from_file())

        data = ""
        doc_done = set()
        done = []
        for m in metrics:

            if not m.type:
                LOG.info('Dropping metric %s because type is not supported', m)
                continue

            if m in done:
                # the pushgateway only allow only one instance of a metric to be pushed in the same request
                # (see https://github.com/prometheus/pushgateway/issues/202)
                LOG.info('Dropping metric %s because already processed in this request', m)
                continue

            if m.name not in doc_done:
                data += "# TYPE %s %s\n" % (m.name, m.type)
                doc_done.add(m.name)


            additional_dimensions = self.common_dimensions_cache.get(m.get_instance_id())
            m.dimensions.update(additional_dimensions)

            dstring = ','.join(['{0}="{1}"'.format(k, v) for k, v in m.dimensions.iteritems()])
            data += '%s{%s} %s\n' % (m.name, dstring, m.value)
            done.append(m)

        self._do_post(data)

        if self.common_dimensions_cache.needs_dump():
            self.common_dimensions_cache.dump_to_file()


    @staticmethod
    def publish_events(events):
        raise NotImplementedError