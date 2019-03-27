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

import json
import requests
from six.moves.urllib import parse as urlparse
from ceilometer.publisher import PublisherBase
from oslo_utils import strutils
from requests import adapters

from ceilometer.openstack.common import log
LOG = log.getLogger(__name__)


import os

class FileConfiguration(object):

    def __init__(self, file_name):
        self._file = file_name
        self.__last_update = 0

        self.reload()

    def needs_save(self):
        raise NotImplemented('Needs to be implemented by subclasses')

    def save(self):
        raise NotImplemented('Needs to be implemented by subclasses')

    def save_if_needed(self):
        if self.needs_save():
            self.save()

    def needs_reload(self):
        if not self._file or not os.path.isfile(self._file):
            return False

        if self.__last_update < os.stat(self._file).st_mtime:
            return True

    def reload_if_needed(self):
        if self.needs_reload():
            self.reload()

    def reload(self):
            self._parse(self._get_file_content())
            self.__last_update = os.stat(self._file).st_mtime if self._file and os.path.isfile(self._file) else 0

    def _get_file_content(self):
        if not self._file or not os.path.isfile(self._file):
            return None
        LOG.debug('File %s reloaded', self._file)
        with open(self._file, 'rb') as file:
            return file.read()

    def _parse(self, content):
        raise NotImplemented('Must be implemented by subclasses')


#
# A backport of the http publisher in the Ceilometer distribution
#
class HttpPublisher(PublisherBase):

    HEADERS = {'Content-type': 'application/json'}

    def __init__(self, parsed_url):
        super(HttpPublisher, self).__init__(parsed_url)

        if not parsed_url.hostname:
            raise ValueError('The hostname of an endpoint for '
                             'HttpPublisher is required')

        # non-numeric port from the url string will cause a ValueError
        # exception when the port is read. Do a read to make sure the port
        # is valid, if not, ValueError will be thrown.
        parsed_url.port

        # Handling other configuration options in the query string
        params = urlparse.parse_qs(parsed_url.query)
        self.max_parallel_requests = self._get_param(params, 'max_parallel_requests', 10, int)
        self.timeout = self._get_param(params, 'timeout', 5, int)
        self.max_retries = self._get_param(params, 'max_retries', 2, int)
        self.poster = (
            self._batch_post if strutils.bool_from_string(self._get_param(
                params, 'batch', True)) else self._individual_post)
        verify_ssl = self._get_param(params, 'verify_ssl', True)
        try:
            self.verify_ssl = strutils.bool_from_string(verify_ssl,
                                                        strict=True)
        except ValueError:
            self.verify_ssl = (verify_ssl or True)

        username = parsed_url.username
        password = parsed_url.password
        if username:
            self.client_auth = (username, password)
            netloc = parsed_url.netloc.replace(username+':'+password+'@', '')
        else:
            self.client_auth = None
            netloc = parsed_url.netloc

        clientcert = self._get_param(params, 'clientcert', None)
        clientkey = self._get_param(params, 'clientkey', None)
        if clientcert:
            if clientkey:
                self.client_cert = (clientcert, clientkey)
            else:
                self.client_cert = clientcert
        else:
            self.client_cert = None

        self.raw_only = strutils.bool_from_string(
            self._get_param(params, 'raw_only', False))

        kwargs = {'max_retries': self.max_retries,
                  'pool_connections': self.max_parallel_requests,
                  'pool_maxsize': self.max_parallel_requests}
        self.session = requests.Session()

        if parsed_url.scheme in ["http", "https"]:
            scheme = parsed_url.scheme
        else:
            ssl = self._get_param(params, 'ssl', False)
            try:
                ssl = strutils.bool_from_string(ssl, strict=True)
            except ValueError:
                ssl = (ssl or False)
            scheme = "https" if ssl else "http"

        # authentication & config params have been removed, so use URL with
        # updated query string
        self.target = urlparse.urlunsplit([
            scheme,
            netloc,
            parsed_url.path,
            urlparse.urlencode(params),
            parsed_url.fragment])

        self.session.mount(self.target, adapters.HTTPAdapter(**kwargs))

        LOG.debug('HttpPublisher for endpoint %s is initialized!' %
                  self.target)

    @staticmethod
    def _get_param(params, name, default_value, cast=None):
        try:
            return cast(params.pop(name)[-1]) if cast else params.pop(name)[-1]
        except (ValueError, TypeError, KeyError):
            LOG.debug('Default value %(value)s is used for %(name)s' %
                      {'value': default_value, 'name': name})
            return default_value

    def _individual_post(self, data):
        for d in data:
            self._do_post(json.dumps(data))

    def _batch_post(self, data):
        if not data:
            LOG.debug('Data set is empty!')
            return
        self._do_post(json.dumps(data))

    def _do_post(self, puburl, data):
        LOG.debug('Message: %s', data)
        try:
            res = self.session.post(puburl, data=data,
                                    headers=self.HEADERS, timeout=self.timeout,
                                    auth=self.client_auth,
                                    cert=self.client_cert,
                                    verify=self.verify_ssl)
            res.raise_for_status()
            LOG.debug('Message posting to %s: status code %d.',
                      puburl, res.status_code)
        except requests.exceptions.HTTPError:
            LOG.exception('Status Code: %(code)s. '
                          'Failed to dispatch message: %(data)s' %
                          {'code': res.status_code, 'data': data})

