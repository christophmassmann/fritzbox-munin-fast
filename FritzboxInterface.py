#!/usr/bin/env python3
"""
  fritzbox_helper - A munin plugin for Linux to monitor AVM Fritzbox
  Copyright (C) 2015 Christian Stade-Schuldt
  Copyright (C) 2019 Rene Walendy
  Author: Christian Stade-Schuldt, Rene Walendy
  Like Munin, this plugin is licensed under the GNU GPL v2 license
  http://www.opensource.org/licenses/GPL-2.0

  Add the following section to your munin-node's plugin configuration:

  [fritzbox_*]
  env.fritzbox_ip [ip address of the fritzbox]
  env.fritzbox_password [fritzbox password]
  env.fritzbox_user [fritzbox user, set any value if not required]

  This plugin supports the following munin configuration parameters:
  #%# family=auto contrib
  #%# capabilities=autoconf

  The initial script was inspired by
  https://www.linux-tips-and-tricks.de/en/programming/389-read-data-from-a-fritzbox-7390-with-python-and-bash
  framp at linux-tips-and-tricks dot de
"""

import hashlib
import sys
import os

import requests
from lxml import etree

class FritzboxInterface:
  """the server address of the Fritzbox (ip or name)"""
  server = "fritz.box"
  """the port the Fritzbox webserver runs on"""
  port = 443
  """the user name to log into the Fritzbox webinterface"""
  user = ""
  """the password to log into the Fritzbox webinterface"""
  password = ""
  useTls = True
  certificateFile = os.getenv('MUNIN_CONFDIR') + '/box.cer'

  __baseUri = ""

  # default constructor
  def __init__(self):
      if os.getenv('fritzbox_ip'):
        self.server = os.getenv('fritzbox_ip')
      self.user = os.getenv('fritzbox_user')
      self.password = os.getenv('fritzbox_password')
      if os.getenv('fritzbox_certificate'):
        self.certificateFile = os.getenv('fritzbox_certificate')
      self.__baseUri = self.__getBaseUri()

  def __getBaseUri(self):
    DEFAULT_PORTS = (80, 443)
    SCHEMES = ('http', 'https')
    if self.port and self.port != DEFAULT_PORTS[self.useTls]:
        return '{}://{}:{}'.format(SCHEMES[self.useTls], self.server, self.port)
    else:
        return '{}://{}'.format(SCHEMES[self.useTls], self.server)

  def getPageWithLogin(self, page, data={}):
    return self.__callPageWithLogin(self.__get, page, data)

  def postPageWithLogin(self, page, data={}):
    return self.__callPageWithLogin(self.__post, page, data)

  def __saveSessionId(self, session_id):
    if '__' in self.server or '__' in self.user:
      raise Exception("Reserved string \"__\" in server or user name")
    statedir = os.getenv('MUNIN_PLUGSTATE') + '/fritzbox'
    if not os.path.exists(statedir):
      os.makedirs(statedir)
    statefilename = statedir + '/' + self.server + '__' + str(self.port) + '__' + self.user + '.sid'
    with open(statefilename, 'w') as statefile:
      statefile.write(session_id)

  def __loadSessionId(self):
    statedir = os.getenv('MUNIN_PLUGSTATE') + '/fritzbox'
    statefilename = statedir + '/' + self.server + '__' + str(self.port) + '__' + self.user + '.sid'
    if not os.path.exists(statefilename):
      return None
    with open(statefilename, 'r') as statefile:
      session_id = statefile.readline()
      return session_id

  def __getSessionId(self):
    """Obtains the session id after login into the Fritzbox.
    See https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/AVM_Technical_Note_-_Session_ID.pdf
    for details (in German).

    :return: the session id
    """

    headers = {"Accept": "application/xml", "Content-Type": "text/plain"}

    url = '{}/login_sid.lua'.format(self.__baseUri)
    try:
      r = requests.get(url, headers=headers, verify=self.certificateFile)
      r.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.SSLError) as err:
      print(err)
      sys.exit(1)

    params = {}
    root = etree.fromstring(r.content)
    session_id = root.xpath('//SessionInfo/SID/text()')[0]
    if session_id == "0000000000000000":
      challenge = root.xpath('//SessionInfo/Challenge/text()')[0]
      challenge_bf = ('{}-{}'.format(challenge, self.password)).encode('utf-16le')
      m = hashlib.md5()
      m.update(challenge_bf)
      response_bf = '{}-{}'.format(challenge, m.hexdigest().lower())
      params['response'] = response_bf
    else:
      return session_id

    params['username'] = self.user

    headers = {"Accept": "text/html,application/xhtml+xml,application/xml", "Content-Type": "application/x-www-form-urlencoded"}

    url = '{}/login_sid.lua'.format(self.__baseUri)
    try:
      r = requests.get(url, headers=headers, params=params, verify=self.certificateFile)
      r.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.SSLError) as err:
      print(err)
      sys.exit(1)

    root = etree.fromstring(r.content)
    session_id = root.xpath('//SessionInfo/SID/text()')[0]
    if session_id == "0000000000000000":
      print("ERROR - No SID received because of invalid password")
      sys.exit(0)

    self.__saveSessionId(session_id)

    return session_id

  def __callPageWithLogin(self, method, page, data={}):
    session_id = self.__loadSessionId()

    if session_id != None:
      try:
        return method(session_id, page, data)
      except (requests.exceptions.HTTPError,
             requests.exceptions.SSLError) as e:
        code = e.response.status_code
        if code != 403:
          print(e)
          sys.exit(1)

    session_id = self.__getSessionId()
    return method(session_id, page, data)

  def __post(self, session_id, page, data={}):
    """Sends a POST request to the Fritzbox and returns the response

    :param session_id: a valid session id
    :param page: the page you are regquesting
    :param data: POST data in a map
    :return: the content of the page
    """

    data['sid'] = session_id

    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

    url = '{}/{}'.format(self.__baseUri, page)

    r = requests.post(url, headers=headers, data=data, verify=self.certificateFile)
    r.raise_for_status()

    return r.content

  def __get(self, session_id, page, data={}):
      """Fetches a page from the Fritzbox and returns its content

      :param session_id: a valid session id
      :param page: the page you are regquesting
      :param params: GET parameters in a map
      :return: the content of the page
      """

      headers = {"Accept": "application/xml", "Content-Type": "text/plain"}

      params = data
      params["sid"] = session_id
      url = '{}/{}'.format(self.__baseUri, page)

      r = requests.get(url, headers=headers, params=params, verify=self.certificateFile)
      r.raise_for_status()

      return r.content
