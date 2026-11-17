'''
*BrightSign* using its built-in API (HTTP Digest authentication)

---

`REV 5 2026.11.17 azuell`

* Control with reboot, screen on/off
* Optional authentication using HTTP Digest authentication
* Optional remote IP binding
* Snapshots on demand

**REVISION HISTORY**

* rev 5: Expand to handle PUT request, Add screen power save mode, video mode, reboot, health
* rev 4: Add authentication, remote IP binding, cleanup logging/status
* rev 3: BrightSign monitoring only using its built-in API (no authentication)

**TO DO**

* multi-output players - currently all outputs hardcoded to 0
* upload/download files

'''

import socket, urllib2
from java.lang import Throwable

socket.setdefaulttimeout(10) # urllib2 has no timeout argument in Jython 2.5

STATUS_CHECK_INTERVAL = 60 # seconds

_ipAddress = None

_authenticationRequired = False
_username = None
_password = None

_lastReceive = 0

param_login = Parameter({'title': 'Brightsign Login', 'schema': {'type': 'object', 'properties': {
  'required': {'title': 'Require Authentication?', 'type': 'boolean', 'order': 1},
  'username': {'title': 'Username', 'type': 'string',  'hint': 'admin', 'order': 2},
  'password': {'title': 'Password', 'type': 'string',  'hint': 'password', 'order': 3}}}})

param_IPAddress = Parameter({'title': 'IP Address', 'schema': {'type': 'string', 'hint': '(overrides bindings)'}})

local_event_IPAddress = LocalEvent({'group': 'Addressing', 'schema': {'type': 'string'}})

def remote_event_IPAddress(arg):
  global _ipAddress
  if is_blank(param_IPAddress):
    previous = local_event_IPAddress.getArg()
    if arg != previous:
      info(0, 'IP address updated to %s (previously %s)' % (arg, previous))
      local_event_IPAddress.emit(arg)
      _ipAddress = arg

local_event_Name        = LocalEvent({'group': 'Information', 'order': 1, 'schema': {'type': 'string'}})
local_event_Desc        = LocalEvent({'group': 'Information', 'order': 2, 'schema': {'type': 'string'}})
local_event_Uptime      = LocalEvent({'group': 'Information', 'order': 3, 'schema': {'type': 'string'}})

local_event_Serial      = LocalEvent({'group': 'Information', 'order': 4, 'schema': {'type': 'string'}})
local_event_Model       = LocalEvent({'group': 'Information', 'order': 5, 'schema': {'type': 'string'}})
local_event_FW          = LocalEvent({'group': 'Information', 'order': 6, 'schema': {'type': 'string'}})
local_event_BootVersion = LocalEvent({'group': 'Information', 'order': 7, 'schema': {'type': 'string'}})

local_event_VideoMode   = LocalEvent({'group': 'Information', 'order': 8, 'schema': {'type': 'string'}})

local_event_Snapshot    = LocalEvent({'group': 'Information', 'order': 9, 'schema': {'type': 'string'}})

local_event_ScreenPower = LocalEvent({'group': 'Control', 'schema': {'type': 'string', 'enum': ['On', 'Off']}})

def main():
  # Get IP address (parameter overrides bindings, otherwise last bound address used)
  global _ipAddress
  _ipAddress = local_event_IPAddress.getArg() if is_blank(param_IPAddress) else param_IPAddress

  # Set login information for authentication if required
  global _authenticationRequired
  global _username, _password
  if param_login and param_login.get('required'):
    _authenticationRequired = True
    _username = param_login.get('username')
    _password = param_login.get('password')

    if is_blank(_username):
      error(0, 'Authentication is required but no username was provided')
    if is_blank(_password):
      error(0, 'Authentication is required but no password was provided')
  else:
    _authenticationRequired = False
    warn(0, 'Authentication marked as not required. Please add log in information if access issues arise')

### HTTP Communications (with Digest authentication)

def requestAPI(path, method='GET', body=None, contentType='application/json'):
  if is_blank(_ipAddress):
    warn(0, 'No IP address (provide one, or bind the IP Address remote event)')
    return

  if _authenticationRequired and (is_blank(_username) or is_blank(_password)):
    warn(0, 'Request not sent: authentication is required but username or password is missing')
    return

  url = 'http://%s%s' % (_ipAddress, path)

  try:
    if not _authenticationRequired:
      return get_url(url, method=method, post=body, contentType=contentType if body else None)

    # get_url can not answer a Digest challenge, but urllib2 can
    passwords = urllib2.HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password(None, url, _username, _password)

    data = (body or '') if method != 'GET' else None
    headers = {'Content-Type': contentType} if body else {}
    request = urllib2.Request(url, data, headers)
    request.get_method = lambda: method # allow PUT DELETE etc beyond GET/POST
    return urllib2.build_opener(urllib2.HTTPDigestAuthHandler(passwords)).open(request).read()

  except (Exception, Throwable), e: # get_url raises Java exceptions
    warn(0, 'Request failed: %s' % e)

### Information and Snapshots

@local_action({'title': 'Get All', 'group': 'Information'})
def Information():
  resp = requestAPI('/api/v1/info', method='GET')
  if resp == None:
    return

  result = json_decode(resp)['data']['result']

  local_event_Uptime.emit(result['upTime'])
  local_event_Name.emit(result['networking']['result']['name'])
  local_event_Desc.emit(result['networking']['result']['description'])

  local_event_Serial.emit(result['serial'])
  local_event_Model.emit(result['model'])
  local_event_FW.emit(result['FWVersion'])
  local_event_BootVersion.emit(result['bootVersion'])

  GetVideoMode.call()
  GetScreenPower.call()

@local_action({'title': 'Get Video Mode', 'group': 'Information'})
def GetVideoMode():
  resp = requestAPI('/api/v1/video-mode/', method='GET')
  if resp == None:
    return

  result = json_decode(resp)['data']['result']

  local_event_VideoMode.emit(result['name'])

@local_action({'title': 'Generate Snapshot', 'group': 'Information'})
def Snapshot():
  resp = requestAPI('/api/v1/snapshot', method='POST')
  if resp == None:
    return

  result = json_decode(resp)['data']['result']
  local_event_Snapshot.emit(result['remoteSnapshotThumbnail'])

### Control

@local_action({'title': 'Reboot', 'group': 'Control'})
def Reboot():
  resp = requestAPI('/api/v1/control/reboot', method='PUT')
  if resp == None:
    return

  info(0, 'Reboot: %s' % json_decode(resp)['data']['result']['message'])

@local_action({'title': 'Screen Power', 'group': 'Control', 'schema': {'type': 'string', 'enum': ['On', 'Off']}})
def ScreenPower(arg):
  # Brightsign closest power approximation: screen on = powersave disabled, screen off = powersave enabled
  resp = requestAPI('/api/v1/video/hdmi/output/0/power-save/', method='PUT', body=json_encode({'enabled': arg == 'Off'}))
  if resp == None:
    return

  GetScreenPower.call()

def remote_event_ScreenPower(arg):
  # Allows another node's On/Off event to drive the screen
  if arg in ('On', 'Off') and arg != local_event_ScreenPower.getArg():
    info(0, 'Screen power requested by binding: %s' % arg)
    ScreenPower.call(arg)

@local_action({'title': 'Get Screen Power', 'group': 'Control'})
def GetScreenPower():
  resp = requestAPI('/api/v1/video/hdmi/output/0/power-save/', method='GET')
  if resp == None:
    return

  # screen off = powersave enabled
  local_event_ScreenPower.emit('Off' if json_decode(resp)['data']['result']['enabled'] else 'On')

### Status

local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})
local_event_Status = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'schema': {'type': 'object', 'properties': {
  'level':   {'type': 'integer', 'order': 1},
  'message': {'type': 'string',  'order': 2}}}})

def CheckHealth():
  resp = requestAPI('/api/v1/health/')
  if resp == None:
    return

  global _lastReceive
  _lastReceive = system_clock()

  return json_decode(resp)['data']['result']['status']

@local_action({'title': 'Poll', 'group': 'Status'})
def StatusCheck():
  health = CheckHealth()

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

    if health == 'active':
      local_event_Status.emit({'level': 0, 'message': 'OK'})
    else:
      local_event_Status.emit({'level': 1, 'message': 'Health: %s' % health})

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
