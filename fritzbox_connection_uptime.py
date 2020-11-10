#!/usr/bin/env python3
"""
  fritzbox_connection_uptime - A munin plugin for Linux to monitor AVM Fritzbox connection uptime
  Copyright (C) 2015 Christian Stade-Schuldt
  Author: Christian Stade-Schuldt
  Like Munin, this plugin is licensed under the GNU GPL v2 license
  http://www.opensource.org/licenses/GPL-2.0
  This plugin requires the fritzconnection plugin. To install it using pip:
  pip install fritzconnection

  Add the following section to your munin-node's plugin configuration:

  [fritzbox_*]
  env.fritzbox_ip [ip address of the fritzbox]

  This plugin supports the following munin configuration parameters:
  #%# family=auto contrib
  #%# capabilities=autoconf
"""

import os
import sys
from fritzconnection.lib.fritzstatus import FritzStatus

def print_uptime():
  try:
    conn = FritzStatus(address=os.getenv('fritzbox_ip'), password=os.getenv('fritzbox_password'), use_tls=True)
  except Exception as e:
    sys.exit("Couldn't get connection uptime: " + str(e))

  uptime = conn.uptime
  print('uptime.value %.2f' % (int(uptime) / 3600.0))

def print_config():
  print("graph_title Connection Uptime")
  print("graph_args --base 1000 -l 0")
  print("graph_vlabel uptime in hours")
  print("graph_scale no")
  print("graph_category network")
  print("uptime.label uptime")
  print("uptime.draw AREA")

if __name__ == "__main__":
  if len(sys.argv) == 2 and sys.argv[1] == 'config':
    print_config()
  elif len(sys.argv) == 2 and sys.argv[1] == 'autoconf':
    print("yes")  # Some docs say it'll be called with fetch, some say no arg at all
  elif len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == 'fetch'):
    try:
      print_uptime()
    except Exception as e:
      sys.exit("Couldn't retrieve fritzbox connection uptime: " + str(e))
