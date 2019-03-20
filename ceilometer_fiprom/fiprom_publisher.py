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
from ceilometer_fiprom.instance_labels import InstanceLabelsCache, NamesMapping, TenantGroupMapping
from ceilometer_fiprom.prom_metric import SampleConverter
from ceilometer_fiprom.util import HttpPublisher

LOG = log.getLogger(__name__)

class PrometheusPublisher(HttpPublisher):
    HEADERS = {'Content-type': 'plain/text'}

    def __init__(self, parsed_url):
        super(PrometheusPublisher, self).__init__(parsed_url)

        # Get configuration from query string
        params = urlparse.parse_qs(parsed_url.query)
        self.cache_file = self._get_param(params, 'cache_file', '/tmp/fiprom_cache', str)
        self.names_file = self._get_param(params, 'names_file', '/opt/fiprom_names', str)
        self.tenant_group_file = self._get_param(params, 'tenant_group_file', '/opt/fiprom_groups', str)
        self.converter_conf_file = self._get_param(params, 'converter_conf_file', '/etc/ceilometer/fiprom_converter.yaml', str)

        LOG.info('using cache_file at %s', self.cache_file)
        LOG.info('using names_file at %s', self.names_file)
        LOG.info('using tenant_group_file at %s', self.tenant_group_file)
        LOG.info('using converter_conf_file at %s', self.converter_conf_file)

        self.instance_labels_cache = InstanceLabelsCache(self.cache_file)
        self.names_mapping = NamesMapping(self.names_file)
        self.tenant_group_mapping = TenantGroupMapping(self.tenant_group_file)
        self.converter = SampleConverter(self.converter_conf_file)

    def publish_samples(self, context, samples):

        if not samples:
            return

        LOG.debug('Got %d samples to publish', len(samples))

        self.converter.reload_if_needed()

        # transform samples to Prometheus metrics
        metrics = [self.converter.get_prom_metric(s) for s in samples]

        # caches instance info that might be in the samples
        map(self.instance_labels_cache.add_instance_info, metrics)

        # update cache with name and tenant group labels
        if self.names_mapping.needs_reload():
            self.names_mapping.reload()
            self.instance_labels_cache.update_names(self.names_mapping.names)

        if self.tenant_group_mapping.needs_reload():
            self.tenant_group_mapping.reload()
            self.instance_labels_cache.update_tenant_groups(self.tenant_group_mapping.names)

        # update metrics with instance labels
        for m in metrics:
            m.update_labels(self.instance_labels_cache.get(m.labels['instance_id']))

        data = ""
        doc_done = set()
        done = []
        for m in metrics:

            if not m.type:
                LOG.info('Dropping metric %s because type is not supported', m)
                continue

            if m in done:
                # The pushgateway only allow only one instance of a metric (same name and same labels) to be pushed
                # in the same request(see https://github.com/prometheus/pushgateway/issues/202)
                # This might happen if there are multiple sample to publish, but apparently Ceilometer call this method
                # always with one sample
                LOG.info('Dropping metric %s because already processed in this request', m)
                continue

            if m.name not in doc_done:
                data += "# TYPE %s %s\n" % (m.name, m.type)
                doc_done.add(m.name)

            labels_string = ','.join(['{0}="{1}"'.format(k, v) for k, v in m.labels.iteritems()])
            data += '%s{%s} %s\n' % (m.name, labels_string, m.value)
            done.append(m)

        self._do_post(data)

        if self.instance_labels_cache.needs_dump():
            self.instance_labels_cache.dump_to_file()

    @staticmethod
    def publish_events(events):
        raise NotImplementedError
