'''
*BrightSign* using its built-in API (HTTP Digest authentication)

---

`REV 4 2026.11.16 azuell`

* Optional authentication using HTTP Digest authentication
* Optional remote IP binding
* Snapshots on demand

**REVISION HISTORY**

* rev 4: Add authentication, remote IP binding, cleanup logging/status
* rev 3: BrightSign monitoring only using its built-in API (no authentication)

'''

import socket, urllib2
from java.lang import Throwable

socket.setdefaulttimeout(10) # urllib2 has no timeout argument in Jython 2.5

DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'password'

STATUS_CHECK_INTERVAL = 60 # seconds

_ipAddress = None

_authenticationRequired = False
_username = None
_password = None

_lastReceive = 0

param_login = Parameter({'title': 'Brightsign Login', 'schema': {'type': 'object', 'properties': {
  'required': {'title': 'Require Authentication?', 'type': 'boolean', 'order': 1},
  'username': {'title': 'Username',                'type': 'string',  'hint': DEFAULT_USERNAME, 'order': 2},
  'password': {'title': 'Password',                'type': 'string',  'hint': DEFAULT_PASSWORD, 'order': 3}}}})

param_IPAddress = Parameter({'title': 'IP Address', 'schema': { 'type': 'string', 'hint': '(overrides bindings)'}})

local_event_IPAddress = LocalEvent({'group': 'Addressing', 'schema': {'type': 'string'}})

def remote_event_IPAddress(arg):
  global _ipAddress
  if is_blank(param_IPAddress):
    previous = local_event_IPAddress.getArg()
    if arg != previous:
      info(0, 'IP address updated to %s (previously %s)' % (arg, previous))
      local_event_IPAddress.emit(arg)
      _ipAddress = arg

local_event_Uptime = LocalEvent({'order': next_seq(), 'schema': {'type': 'string'}})
local_event_Name = LocalEvent({'order': next_seq(), 'schema': {'type': 'string'}})
local_event_Desc = LocalEvent({'order': next_seq(), 'schema': {'type': 'string'}})

local_event_Serial = LocalEvent({'group': 'Information', 'schema': {'type': 'string', 'order': next_seq()}})
local_event_Model = LocalEvent({'group': 'Information', 'schema': {'type': 'string', 'order': next_seq()}})
local_event_FW = LocalEvent({'group': 'Information', 'schema': {'type': 'string', 'order': next_seq()}})
local_event_BootVersion = LocalEvent({'group': 'Information', 'schema': {'type': 'string', 'order': next_seq()}})

local_event_Snapshot = LocalEvent({ 'schema': { 'type': 'string' }})

local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})
local_event_Status = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'schema': {'type': 'object', 'properties': {
  'level':   {'type': 'integer', 'order': 1},
  'message': {'type': 'string',  'order': 2}}}})

def main():
  # Get IP address (parameter overrides bindings, otherwise last bound address used)
  global _ipAddress
  _ipAddress = local_event_IPAddress.getArg() if is_blank(param_IPAddress) else param_IPAddress

  # Set login information for authentication if required
  global _authenticationRequired
  global _username, _password
  if param_login and param_login.get('required'):
    _authenticationRequired = True
    _username = DEFAULT_USERNAME if 'username' not in param_login else param_login.get('username')
    _password = DEFAULT_PASSWORD if 'password' not in param_login else param_login.get('password')
  else:
    _authenticationRequired = False
    warn(0, 'Authentication marked as not required. Please add log in information if access issues arise')

### HTTP Communications (with Digest authentication)

def requestAPI(path, method='GET'):
  if is_blank(_ipAddress):
    warn(0, 'No IP address (provide one, or bind the IP Address remote event)')
    return

  url = 'http://%s%s' % (_ipAddress, path)

  try:
    if not _authenticationRequired:
      return get_url(url, method=method)

    # get_url can not answer a Digest challenge, but urllib2 can
    passwords = urllib2.HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password(None, url, _username, _password)
    return urllib2.build_opener(urllib2.HTTPDigestAuthHandler(passwords)).open(url, '' if method == 'POST' else None).read()
  
  except (Exception, Throwable), e: # get_url raises Java exceptions
    warn(0, 'Request failed: %s' % e)

### Information and Snapshots

@local_action({'title': 'Poll', 'group': 'Information'})
def Information():
  resp = requestAPI('/api/v1/info', method='GET')
  if resp == None:
    return

  global _lastReceive
  _lastReceive = system_clock()

  result = json_decode(resp)['data']['result']

  local_event_Uptime.emit(result['upTime'])
  local_event_Name.emit(result['networking']['result']['name'])
  local_event_Desc.emit(result['networking']['result']['description'])

  local_event_Serial.emit(result['serial'])
  local_event_Model.emit(result['model'])
  local_event_FW.emit(result['FWVersion'])
  local_event_BootVersion.emit(result['bootVersion'])

@local_action({ 'title': 'Generate Snapshot' })
def Snapshot():
  resp = requestAPI('/api/v1/snapshot', method='POST')
  if resp == None:
    return

  result = json_decode(resp)['data']['result']
  local_event_Snapshot.emit(result['remoteSnapshotThumbnail'])

### Status

@local_action({'title': 'Poll', 'group': 'Status'})
def StatusCheck():
  # Poll the device, then check how long ago it last answered
  Information.call()

  diff = (system_clock() - _lastReceive) / 1000.0 # in secs

  if diff > STATUS_CHECK_INTERVAL:
    previous_contact_value = local_event_LastContactDetect.getArg()

    if previous_contact_value == None:
      message = 'Never seen'
    else:
      previous_contact = date_parse(previous_contact_value)
      message = 'Missing %s' % FormatPeriod(previous_contact)
    local_event_Status.emit({'level': 2, 'message': message})

  else:
    local_event_LastContactDetect.emit(str(date_now()))
    local_event_Status.emit({'level': 0, 'message': 'OK'})

Timer(lambda: StatusCheck.call(), STATUS_CHECK_INTERVAL, 5)

def FormatPeriod(date):
  """Takes in a date object and returns the phrase to be displayed in the dashboard"""

  if date == None:
    return 'for unknown period'

  time_difference = (date_now().getMillis() - date.getMillis()) / 1000 / 60 # in mins

  if time_difference < 0:
    return 'never ever'
  elif time_difference == 0:
    return 'for <1 min'
  elif time_difference < 60:
    return 'for <%s mins' % time_difference
  elif time_difference < 60*24:
    return 'since %s' % date.toString('h:mm:ss a')
  else:
    return 'since %s' % date.toString('E d-MMM h:mm:ss a')

### Logging

local_event_LogLevel = LocalEvent({'group': 'Debug', 'order': 100000 + next_seq(), 'desc': 'Use this to ramp up the logging (with indentation)', 'schema': {'type': 'integer'}})

@local_action({'group': 'Debug', 'title': '+', 'order': 100000 + next_seq() })
def increaseLogLevel():
  local_event_LogLevel.emit((local_event_LogLevel.getArg() or 0) + 1)

@local_action({'group': 'Debug', 'title': '-', 'order': 100000 + next_seq() })
def decreaseLogLevel():
  local_event_LogLevel.emit((local_event_LogLevel.getArg() or 0) - 1)

def info(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.info(('  ' * level) + msg)

def error(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.error(('  ' * level) + msg)

def warn(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.warn(('  ' * level) + msg)

def log(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.log(('  ' * level) + msg)
