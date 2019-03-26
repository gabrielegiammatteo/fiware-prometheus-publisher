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

from ceilometer import sample
from ceilometer.storage.impl_log import Connection
import traceback
import sys
from ceilometer.openstack.common import log
from ceilometer_fiprom.fiprom_publisher import PrometheusPublisher
import urlparse
LOG = log.getLogger(__name__)

class PrometheusStorage(Connection):

    _publisher = None

    def __init__(self, url):
        super(PrometheusStorage, self).__init__(url)
        self.parsed_url = urlparse.urlparse(url)

        params = urlparse.parse_qs(self.parsed_url.query)
        self.logfile = params.get('log_file', [None])[0]
        if self.logfile:
            LOG.info('Logging received events to %s', self.logfile)


    def __get_publisher(self):
        if not self._publisher:
            try:
                self._publisher = PrometheusPublisher(self.parsed_url)
            except:
                traceback.print_exc(file=sys.stdout)

        return self._publisher

    def record_metering_data(self, data):

        # data is a dictionary such as returned by ceilometer.meter.meter_message_from_counter

        if self.logfile:
            with open(self.logfile, 'a+') as c:
                c.write('{0}\n'.format(data))

        # transform a message to sample
        s = sample.Sample(data['counter_name'],
                          data['counter_type'],
                          data['counter_unit'],
                          data['counter_volume'],
                          data['user_id'],
                          data['project_id'],
                          data['resource_id'],
                          data['timestamp'],
                          None,
                          source = data['source'])

        if 'resource_metadata' in data and data['resource_metadata']:
            s.resource_metadata = {k: v for k, v in data['resource_metadata'].iteritems() if v is not None}

        try:
            self.__get_publisher().publish_samples(None, [s])
        except:
            traceback.print_exc(file=sys.stderr)
