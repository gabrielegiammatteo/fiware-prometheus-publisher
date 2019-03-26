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
from ceilometer_fiprom.metric_enrichment import NamesEnricher, TenantGroupEnricher, InstanceEnricher
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
        self.dryrun = self._get_param(params, 'dryrun', False, bool)

        LOG.info('using cache_file at %s', self.cache_file)
        LOG.info('using names_file at %s', self.names_file)
        LOG.info('using tenant_group_file at %s', self.tenant_group_file)
        LOG.info('using converter_conf_file at %s', self.converter_conf_file)
        LOG.info('Logging received events to %s', self.logfile)
        LOG.info('dryrun = %s', self.dryrun)

        self.converter = SampleConverter(self.converter_conf_file)

        self.enrichers = [
            # first use the Instance Enricher because it might adds new IDs that can be enriched by the other ones
            InstanceEnricher(self.cache_file),
            NamesEnricher(self.names_file),
            TenantGroupEnricher(self.tenant_group_file)
        ]

        # remove used params from the query string
        parsed_url = parsed_url._replace(query=urllib.urlencode(params))
        self.pub_url = parsed_url._replace(query='')._replace(scheme='http')
        super(PrometheusPublisher, self).__init__(parsed_url)


    def publish_samples(self, context, samples):

        # reload config files
        self.converter.reload_if_needed()
        for e in self.enrichers:
            e.reload_if_needed()

        # convert samples to metrics
        metrics = [self.converter.get_prom_metric(s) for s in samples]
        metrics = [m for m in metrics if m is not None]

        # update caches of enrichers (only InstanceEnricher at the moment)
        for e in self.enrichers:
            for m in metrics:
                e.updateCache(m)

        for m in metrics:

            # invoke enrichers to add labels
            for e in self.enrichers:
                e.enrichLabels(m)


            puburl = self.__build_publication_url(m)
            pubcon = self.__build_publication_content(m)

            if not self.dryrun:
                self._do_post(puburl, pubcon)

            if self.logfile:
                with open(self.logfile, 'a+') as c:
                    c.write('{0}\n{1}\n'.format(urlparse.urlunparse(puburl), pubcon))

        for e in self.enrichers:
            e.save_if_needed()

    def __build_publication_content(self, metric):
        keys = metric.labels.keys()
        keys.sort()
        labels = ','.join(['{0}="{1}"'.format(k, metric.labels[k]) for k in keys if not k.startswith('__')])
        return "# TYPE {0} {1}\n{0}{{{2}}} {3}\n".format(metric.name, metric.type, labels, metric.value)

    def __build_publication_url(self, metric):
        grouping_keys = metric.labels['__grouping_key']
        pubpath = self.pub_url.path +'/' + '/'.join(['{0}/{1}'.format(k, metric.labels[k]) for k in grouping_keys if k in metric.labels])
        return self.pub_url._replace(path=pubpath)

    @staticmethod
    def publish_events(events):
        raise NotImplementedError
