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

import urllib
from six.moves.urllib import parse as urlparse
from ceilometer.openstack.common import log
from ceilometer_fiprom.instance_labels import InstanceLabelsCache, NamesMapping, TenantGroupMapping
from ceilometer_fiprom.prom_metric import SampleConverter
from ceilometer_fiprom.util import HttpPublisher

LOG = log.getLogger(__name__)

class PrometheusPublisher(HttpPublisher):
    HEADERS = {'Content-type': 'plain/text'}

    def __init__(self, parsed_url):

        # Get configuration from query string
        params = urlparse.parse_qs(parsed_url.query)
        self.cache_file = self._get_param(params, 'cache_file', '/tmp/fiprom_cache', str)
        self.names_file = self._get_param(params, 'names_file', '/opt/fiprom_names', str)
        self.tenant_group_file = self._get_param(params, 'tenant_group_file', '/opt/fiprom_groups', str)
        self.converter_conf_file = self._get_param(params, 'converter_conf_file', '/etc/ceilometer/fiprom_converter.yaml', str)
        self.logfile = self._get_param(params, 'log_file', None, str)

        LOG.info('using cache_file at %s', self.cache_file)
        LOG.info('using names_file at %s', self.names_file)
        LOG.info('using tenant_group_file at %s', self.tenant_group_file)
        LOG.info('using converter_conf_file at %s', self.converter_conf_file)
        LOG.info('Logging received events to %s', self.logfile)

        self.instance_labels_cache = InstanceLabelsCache(self.cache_file)
        self.names_mapping = NamesMapping(self.names_file)
        self.tenant_group_mapping = TenantGroupMapping(self.tenant_group_file)
        self.converter = SampleConverter(self.converter_conf_file)

        # remove used params from the query string
        parsed_url = parsed_url._replace(query=urllib.urlencode(params))
        self.pub_url = parsed_url._replace(query='')._replace(scheme='http')
        super(PrometheusPublisher, self).__init__(parsed_url)


    def publish_samples(self, context, samples):
        self.converter.reload_if_needed()

        metrics = [self.converter.get_prom_metric(s) for s in samples]

        map(self.instance_labels_cache.add_instance_info, metrics)

        # update cache with name and tenant group labels
        if self.names_mapping.needs_reload():
            self.names_mapping.reload()
            self.instance_labels_cache.update_names(self.names_mapping.names)

        if self.tenant_group_mapping.needs_reload():
            self.tenant_group_mapping.reload()
            self.instance_labels_cache.update_tenant_groups(self.tenant_group_mapping.names)

        for m in metrics:

            if not m.type:
                LOG.warning('Dropping metric because type is not supported: %s', m)
                continue

            m.update_labels(self.instance_labels_cache.get(m.labels['__cache_key']))
            grouping_keys = m.labels['__grouping_key']
            pubpath = self.pub_url.path +'/' + '/'.join(['{0}/{1}'.format(k, m.labels[k]) for k in grouping_keys if k in m.labels])

            labels = ','.join(['{0}="{1}"'.format(k, v) for k, v in m.labels.iteritems() if not k.startswith('__')])

            data = "# TYPE {0} {1}\n{0}{{{2}}} {3}\n".format(m.name, m.type, labels, m.value)

            self._do_post(self.pub_url._replace(path=pubpath), data)

            if self.logfile:
                with open(self.logfile, 'a+') as c:
                    c.write('{0}\n'.format(data))

        if self.instance_labels_cache.needs_dump():
            self.instance_labels_cache.dump_to_file()

    @staticmethod
    def publish_events(events):
        raise NotImplementedError
