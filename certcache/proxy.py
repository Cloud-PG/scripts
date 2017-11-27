#!/bin/env python
"""This script requires the following environment variables:

  - IAM_TOKEN
  - IAM_REFRESH_TOKEN
  - IAM_CLIENT_ID
  - IAM_CLIENT_SECRET
  - MARATHON_USER
  - MARATHON_PASSWD

"""
from __future__ import print_function

import json
import logging
import os
import subprocess
import sys
import time
from StringIO import StringIO

import requests
from urllib3._collections import HTTPHeaderDict

import pycurl
from cache import *

if sys.version_info.major == 2:
    from urlparse import urlsplit
else:
    from urllib.parse import urlsplit


class ProxyManager(object):

    """Manager of tokens."""

    def __init__(self, env, cache_manager=None):
        # Get all environment variables
        self.iam_token = env.get('IAM_TOKEN')
        self.client_id = env.get('IAM_CLIENT_ID')
        self.client_secret = env.get('IAM_CLIENT_SECRET')
        self.marathon = {
            'user': env.get('MARATHON_USER'),
            'passwd': env.get('MARATHON_PASSWD')
        }
        # CACHE
        self.cache_dir = '/tmp'
        if cache_manager == 'ZOOKEEPER':
            self.cache = ZookeeperCache(env.get('ZOOKEEPER_HOST_LIST'))
        elif cache_manager == 'MARATHON':
            self.cache = MarathonCache(
                self.marathon['user'], self.marathon['passwd'])
        else:
            self.cache = MemoryCache()
        ##
        self.token_expiration = 600000
        self.age = 20
        self.audience = 'https://watts-dev.data.kit.edu'
        self.tts = 'https://watts-dev.data.kit.edu'
        self.iam_endpoint = 'https://iam-test.indigo-datacloud.eu/'
        self.token_endpoint = self.iam_endpoint + 'token'
        self.introspect_endpoint = self.iam_endpoint + 'introspect'
        self.credential_endpoint = 'https://watts-dev.data.kit.edu/api/v2/iam/credential'
        self.tts_output_data = '{}/output.json'.format(self.cache_dir)
        self.lock_file = "{}/lock".format(self.cache_dir)
        self.user_cert = "{}/usercert.crt".format(self.cache_dir)
        self.user_key = "{}/userkey.key".format(self.cache_dir)
        self.user_passwd = "{}/userpasswd.txt".format(self.cache_dir)
        self.user_proxy = "{}/userproxy.pem".format(self.cache_dir)
        self.exchanged_token = ""

    def check_tts_data(self):
        """Checks and refresh tts data.

        Workflow:
            - Check cached TTS data
                - if exists and it's up to date -> ok
                - if it's not up to date -> refresh
                - else -> exchange token
        """
        logging.debug("Check tts output data: %s", self.tts_output_data)
        if os.path.exists(self.tts_output_data):
            ctime = os.stat(self.tts_output_data).st_ctime
            since = time.time() - ctime
            logging.debug("Check expiration time: %s > %s",
                          since, self.token_expiration)
            if since > self.token_expiration:
                logging.debug("Token about to expire. Get tts data...")
                tts_data = self.get_tts_data(True)
            else:
                logging.debug("Token OK.")
                return True
        else:
            logging.debug("Token not exist, get exchange token...")
            self.exchanged_token = self.get_exchange_token()
            if isinstance(self.exchanged_token, int):
                logging.error("Get exchange token error: %s",
                              self.exchanged_token)
                if self.cache.refresh_token.value == '':
                    logging.error("Problem with Token Server")
                    return False
                else:
                    logging.error("Exchange with refresh token")
                    tts_data = self.get_tts_data(True)
            else:
                logging.debug("Token OK.")
                tts_data = self.get_tts_data(self.exchanged_token)

        return tts_data

    def get_certificate(self, url):
        """Retrieve the certificate.

        Returns:
            The given tts token

        Raises:
            - redirect errors
            - curl errors

        TO DO:
            - Manage controls (gestisci controlli)
        """
        bearer = 'Authorization: Bearer ' + \
            str(self.exchanged_token).split('\n', 1)[0]
        data = json.dumps({"service_id": "x509"})

        logging.debug("Create headers and buffers")
        headers = StringIO()
        buffers = StringIO()

        logging.debug("Prepare CURL")
        curl = pycurl.Curl()
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.HTTPHEADER, [
                    bearer, 'Content-Type: application/json'])
        curl.setopt(pycurl.POST, 1)
        curl.setopt(pycurl.POSTFIELDS, data)
        curl.setopt(curl.WRITEFUNCTION, buffers.write)
        curl.setopt(curl.HEADERFUNCTION, headers.write)
        curl.setopt(curl.VERBOSE, True)

        try:
            logging.debug("Perform CURL call")
            curl.perform()
            status = curl.getinfo(curl.RESPONSE_CODE)
            logging.debug("Result status: %s", status)
            logging.debug("Close CURL")
            curl.close()
            logging.debug("Get body content")
            body = buffers.getvalue()
            logging.debug("Body: %s", body)

            if str(status) != "303":
                logging.error(
                    "On 'get redirected with curl': http error: %s", str(status))
                return False
        except pycurl.error as error:
            errno, errstr = error
            logging.error('A pycurl error n. %s occurred: %s', errno, errstr)
            return False

        logging.debug("Manage redirect")
        for item in headers.getvalue().split("\n"):
            if "location" in item:
                # Example item
                #   "location: https://watts-dev.data.kit.edu/api/v2/iam/credential_data/xxx"
                logging.debug("Item url: %s", item)
                url_path = urlsplit(item.strip().split()[1]).path
                redirect = self.tts + url_path
                logging.debug("Redirect location: %s", redirect)

                headers = {'Authorization': 'Bearer ' +
                           self.exchanged_token.strip()}
                response = requests.get(redirect, headers=headers)

                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as err:
                    # Whoops it wasn't a 200
                    logging.error(
                        "Error in get certificate redirect: %s", str(err))
                    return False

                with open('/tmp/output.json', 'w') as outf:
                    outf.write(response.content)
            else:
                logging.error("No location in redirect response")

        return True

    def get_exchange_token(self):
        """Retrieve the access token.

        Exchange the access token with the given client id and secret.
        The refresh token in cached and the exchange token is kept in memory.

        TO DO:
            - Add controls (aggiungi controlli)
        """

        logging.debug("Prepare header")

        data = HTTPHeaderDict()
        data.add('grant_type', 'urn:ietf:params:oauth:grant-type:token-exchange')
        data.add('audience', self.audience)
        data.add('subject_token', self.iam_token)
        data.add('scope', 'openid profile offline_access')

        logging.debug("Call get exchanged token with data: %s", data)

        response = requests.post(self.token_endpoint, data=data, auth=(
            self.client_id, self.client_secret), verify=True)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            # Whoops it wasn't a 200
            logging.error("Error in get exchange token: %s", err)
            return response.status_code

        result = json.loads(response.content)
        logging.debug("Result: %s", result)

        logging.debug("Override refresh token")
        with open('/tmp/refresh_token', 'w') as outf:
            outf.write(result["refresh_token"])
            self.cache.refresh_token.value = result["refresh_token"]

        return result["access_token"]

    def introspection(self, iam_client_id, iam_client_secret, exchanged_token):
        """Get info through introspection with the given client id, secret and token.

        TO DO:
            - Add controls (aggiungi controlli)
        """

        iam_client_id = self.client_id
        iam_client_secret = self.client_secret

        data = HTTPHeaderDict()
        data.add('token', exchanged_token)

        response = requests.post(self.introspect_endpoint, data=data, auth=(
            iam_client_id, iam_client_secret), verify=False)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            # Whoops it wasn't a 200
            logging.error("Error in introspection: %s", err)
            logging.error("HTTP error. Response status: %s",
                          response.status_code)
            return response.status_code

        with open('/tmp/introspection', 'w') as outf:
            outf.write(response.content)

    def refresh_token(self, refresh_token):
        """Request with refresh token.

        TO DO:
            - Manage result out of the function (gestisci result fuori dalla funzione)
        """
        data = HTTPHeaderDict()
        data.add('client_id', self.client_id)
        data.add('client_secret', self.client_secret)
        data.add('grant_type', 'refresh_token')
        data.add('refresh_token', refresh_token)

        logging.debug("Refresh token. data: %s", data)

        response = requests.post(self.token_endpoint, data=data, verify=True)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            # Whoops it wasn't a 200
            logging.error("Error in refresh_token: %s", err)
            logging.error("HTTP error. Response status: %s",
                          response.status_code)
            return response.status_code

        logging.debug("Response content: %s", response.content)
        result = json.loads(response.content)
        return result["access_token"]

    def get_tts_data(self, exchange=False):
        """Get TTS data using a lock procedure.

        Phases:
            - get lock
            - retrieve_tts_data
            - release lock

        Params:
            exchange (Bool): indicate if we have to do the exchange
        """
        logging.debug("Check lock file %s", self.lock_file)
        if os.path.exists(self.lock_file):
            ctime = os.stat(self.lock_file).st_ctime
            age = time.time() - ctime
            logging.debug("Check age of %s: %s < %s",
                          self.lock_file, age, self.age)
            if age < self.age:
                logging.debug("Update in progres. Go to sleep...")
                time.sleep(self.age - age)
            else:
                logging.debug("Stale lock file. Removing %s...",
                              self.lock_file)
                os.remove(self.lock_file)
        logging.debug("Update last use time of %s", self.lock_file)
        open(self.lock_file, 'w+').close()

        if exchange:
            logging.debug("Exchange /tmp/refresh_token")
            if self.cache.refresh_token.value == "":
                with file('/tmp/refresh_token') as refresh_t_file:
                    refresh_token = refresh_t_file.read()
                    logging.debug("Refresh token")
                    self.exchanged_token = self.refresh_token(
                        refresh_token.strip())
                    if isinstance(self.exchanged_token, int):
                        logging.error("Error in refresh_token")
            else:
                self.exchanged_token = self.refresh_token(
                    self.cache.refresh_token.value)
                if isinstance(self.exchanged_token, int):
                    logging.error("Error in refresh_token with Zookeeper")
                else:
                    with open('/tmp/refresh_token', 'w') as outf:
                        outf.write(self.cache.refresh_token.value)

        logging.debug("Refresh token")
        if self.get_certificate(self.credential_endpoint):

            logging.debug("Load json and prepare objects")
            with open('/tmp/output.json') as tts_data_file:
                tts_data = json.load(tts_data_file)

            with open(self.user_cert, 'w+') as cur_file:
                cur_file.write(
                    str(tts_data['credential']['entries'][0]['value']))

            with open(self.user_key, 'w+') as cur_file:
                cur_file.write(
                    str(tts_data['credential']['entries'][1]['value']))

            with open(self.user_passwd, 'w+') as cur_file:
                cur_file.write(
                    str(tts_data['credential']['entries'][2]['value']))

            try:
                logging.debug("Change user key mod")
                os.chmod(self.user_key, 0o600)
            except OSError as err:
                logging.error(
                    "Permission denied to chmod passwd file: %s", err)
                return False

            logging.debug("Remove lock")
            os.remove(self.lock_file)

            return True

        return False

    def generate_proxy(self):
        """Generates proxy with grid-proxy-init only if there are not errors."""

        if self.check_tts_data():
            logging.debug("Generating proxy for %s", self.exchanged_token)

            command = "grid-proxy-init -valid 160:00 -key {} -cert {} -out {} -pwstdin ".format(
                self.user_key, self.user_cert, self.user_proxy
            )
            with open(self.user_passwd) as my_stdin:
                my_passwd = my_stdin.read()
            proxy_init = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            )

            logging.debug("Execute proxy")
            proxy_out, proxy_err = proxy_init.communicate(input=my_passwd)

            logging.debug("Proxy result: %s", proxy_init.returncode)
            if proxy_init.returncode > 0:
                logging.error("grid-proxy-init failed for token %s",
                              self.exchanged_token)
                logging.error("grid-proxy-init failed stdout %s", proxy_out)
                logging.error("grid-proxy-init failed stderr %s", proxy_err)
            else:
                return self.user_proxy
        else:
            logging.error("Error occured in check_tts_data!")


def get():
    """Execute the get_proxy routine."""
    logging.info("CALLING GET PROXY")

    # imports tokens, id and secret
    ENV = {
        'IAM_TOKEN': os.environ.get("IAM_TOKEN", None),
        'IAM_REFRESH_TOKEN': os.environ.get("IAM_REFRESH_TOKEN", None),
        'IAM_CLIENT_ID': os.environ.get("IAM_CLIENT_ID", None),
        'IAM_CLIENT_SECRET': os.environ.get("IAM_CLIENT_SECRET", None),
        'MARATHON_USER': os.environ.get("MARATHON_USER", None),
        'MARATHON_PASSWD': os.environ.get("MARATHON_PASSWD", None),
        'ZOOKEEPER_HOST_LIST': os.environ.get("ZOOKEEPER_HOST_LIST", None),
        'CACHE_MANAGER': os.environ.get("CACHE_MANAGER", False)
    }

    logging.info("IAM_TOKEN = %s", ENV.get('IAM_TOKEN'))
    logging.info("IAM_REFRESH_TOKEN = %s", ENV.get('IAM_REFRESH_TOKEN'))
    logging.info("IAM_CLIENT_= %s", ENV.get('IAM_CLIENT_ID'))
    logging.info("IAM_CLIENT_SECRET = %s", ENV.get('IAM_CLIENT_SECRET'))
    logging.info("MARATHON_USER = %s", ENV.get('MARATHON_USER'))
    logging.info("MARATHON_PASSWD = %s", ENV.get('MARATHON_PASSWD'))
    logging.info("ZOOKEEPER_HOST_LIST = %s", ENV.get('ZOOKEEPER_HOST_LIST'))
    logging.info("CACHE_MANAGER = %s", ENV.get('CACHE_MANAGER'))

    cache_manager = None

    if ENV.get('CACHE_MANAGER') == 'ZOOKEEPER' and ENV.get('ZOOKEEPER_HOST_LIST') is not None:
        cache_manager = 'ZOOKEEPER'
    elif ENV.get('CACHE_MANAGER') == 'MARATHON' and ENV.get('MARATHON_USER') is not None and ENV.get('MARATHON_PASSWD') is not None:
        cache_manager = 'MARATHON'
    elif ENV.get('CACHE_MANAGER'):
        # CACHE MANAGER is set and is not recognized
        raise Exception("Unknown CACHE MANAGER")

    proxy_manager = ProxyManager(ENV, cache_manager)
    proxy_file = proxy_manager.generate_proxy()

    if proxy_file is not None:
        header = {
            'Content-Type': "application/octet-stream",
            'filename': ".pem"
        }
        with open(proxy_file, 'rb') as file_:
            data = file_.read()
        return header, data
    else:
        logging.error("Cannot find Proxy file: '%s'", proxy_file)
        header = {
            'Content-Type': "text/html"
        }
        return header, "<p>grid-proxy-info failed</p>"