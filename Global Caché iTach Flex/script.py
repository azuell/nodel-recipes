'''
Global Cache **iTach Flex IP Ethernet PoE**

---

`REV 2 2026.07.14 azuell`

* Using the Global Cache Unified API over TCP
* For use with Flex Link Cables - Infrared, Serial, Relay and Sensor

**MANUAL**

* [iTach Flex Datasheet](https://www.globalcache.com/files/docs/ds_Flex_print.pdf)
* [Flex and Flex Link Cables User Guide](https://www.globalcache.com/files/releases/flex/ug-gc-flex_flc.pdf)
* [Global Cache Unified TCP API V1.1.2](https://www.globalcache.com/files/docs/api-gc-unifiedtcp.pdf)

**REVISION HISTORY**

* _rev. 2: Update for sharing_
* _rev. 1: Initial release_
'''

CONTROL_PORT = 4998

STATUS_CHECK_INTERVAL = 30 #s

ERROR_CODES = {
  # Common
  '001':   'Invalid command (unknown).',
  '002':   'Invalid command syntax.',
  '003':   'Invalid module address or port address.',
  '004':   'No carriage return.',
  '005':   'Not supported.',

  # Infrared Errors
  'IR001': 'Invalid ID.',
  'IR002': 'Invalid frequency.',
  'IR003': 'Invalid repeat.',
  'IR004': 'Invalid offset.',
  'IR005': 'Invalid pulsecount.',
  'IR006': 'Uneven pulsecounts.',
  'IR007': 'Code too long.',

  # Serial Errors
  'SL001': 'Invalid baud rate.',
  'SL002': 'Invalid flow control.',
  'SL003': 'Invalid parity value.',
  'SL004': 'Invalid stop bits value.',
  'SL006': 'Invalid duplex value.',
  'SL007': 'Invalid gender.',

  # Relay & Sensor Errors
  'RO001': 'Invalid logical relay type.',
  'RO002': 'Invalid logical relay state.',
  'RO003': 'Unsupported operation.',
  'RO004': 'Logical relay disabled/unavailable.',
  'SI001': 'Sensor not available.',
  'SI002': 'Invalid sensor notify port value.',
  'SI003': 'Invalid sensor notify time value.',
}

param_disabled = Parameter({'title': 'Disable Node', 'order': 1, 'schema': {'type': 'boolean'}})

param_ipAddress = Parameter({'title': 'IP Address', 'order': 2, 'schema': {'type': 'string', 'hint': 'will override bindings'}})

local_event_IPAddress = LocalEvent({'group': 'Information', 'title': 'IP Address (via binding)', 'schema': {'type': 'string'}})
local_event_Version = LocalEvent({'group': 'Information', 'title': 'Firmware version', 'schema': {'type': 'string'}})
local_event_HostType = LocalEvent({'group': 'Information', 'title': 'Network interface', 'schema': {'type': 'string'}})
local_event_DeviceType = LocalEvent({'group': 'Information', 'title': 'Flex Link cable type', 'schema': {'type': 'string'}})
local_event_Network = LocalEvent({'group': 'Information', 'title': 'Network settings', 'schema': {'type': 'object', 'properties': {
  'configLock': {'type': 'string', 'order': 1},
  'ipConfig':   {'type': 'string', 'order': 2},
  'ipAddress':  {'type': 'string', 'order': 3},
  'subnet':     {'type': 'string', 'order': 4},
  'gateway':    {'type': 'string', 'order': 5}}}})

def remote_event_IPAddress(arg):
  if arg and same_value(arg, local_event_IPAddress.getArg()):
    return

  local_event_IPAddress.emit(arg)
  SetupTCP()

### TCP

def tcp_connected():
  info(0, 'tcp_connected')

  SetupDevice()

def tcp_disconnected():
  warn(0, 'tcp_disconnected')

def tcp_timeout():
  log(0, 'tcp_timeout')

def tcp_sent(data):
  log(2, 'tcp_sent [%s]' % data)

def tcp_received(data):
  log(2, 'tcp_received [%s]' % data)

  global _lastReceive
  _lastReceive = system_clock() # any response is proof of presence

  if ParseError(data):
    return

  ParseDeviceType(data)
  ParseRelayState(data)
  ParseSensorState(data)

def SetupTCP():
  newDest = None
  
  if param_ipAddress:
    newDest = '%s:%s' % (param_ipAddress, CONTROL_PORT)
    info(0, 'Setting dest from params [%s]' % newDest)
    
  elif local_event_IPAddress.getArg():
    newDest = '%s:%s' % (local_event_IPAddress.getArg(), CONTROL_PORT)
    info(0, 'Setting dest from binding [%s]' % newDest)
    
  else:
    warn(0, 'IP params or IP binding not specified!')
    return
  
  tcp.setDest(newDest)

tcp = TCP(connected=tcp_connected, 
          disconnected=tcp_disconnected, 
          sent=tcp_sent,
          received=tcp_received,
          timeout=tcp_timeout, 
          sendDelimiters='\r', 
          receiveDelimiters='\r\n')

### Main

def main():
  info(0, 'Started!')

  if param_disabled:
    warn(0, 'Node is disabled; will not connect TCP')
    return

  SetupTCP()

### Error Checking

def ParseError(resp):
  resp = (resp or '')

  if not resp.startswith('ERR'):
    return False

  code = resp[3:].strip(' _:,')
  description = ERROR_CODES.get(code, 'Unknown error code')

  warn(0, 'tcp_received - device returned error [%s] %s' % (resp, description))

  return True

### Setup Flex device

def SetupDevice():

  def handleVersion(resp):
    info(0, 'SetupDevice - firmware version [%s]' % resp)
    local_event_Version.emit(resp)
    tcp.send('getdevices')

  tcp.request('getversion', handleVersion)

def ParseDeviceType(resp):
  resp = (resp or '').strip()

  if resp == 'endlistdevices':
    # getdevices end, can setup action/events based on device type
    if local_event_DeviceType.getArg() == 'RELAYSENSOR':
      SetupRelays()
      SetupSensors()

    GetNetwork.call() # only query network config once getdevices has fully finished
    return

  # Flex Link network interface
  if resp.startswith('device,0,0'):
    hostType = resp.split(' ', 1)[1].strip()
    info(0, 'SetupDevice - network interface [%s]' % hostType)
    local_event_HostType.emit(hostType)
    return

  # Flex Link cable type
  if resp.startswith('device,1,1'):
    deviceType = resp.split(' ', 1)[1].strip()
    info(0, 'SetupDevice - Flex Link cable type [%s]' % deviceType)
    local_event_DeviceType.emit(deviceType)
    return

@local_action({'title': 'Get Network', 'group': 'Information'})
def GetNetwork():

  def handleNetwork(resp):
    parts = resp.split(',')

    if len(parts) != 7 or parts[0] != 'NET':
      warn(0, 'GetNetwork - unexpected response [%s]' % resp)
      return

    configLock, ipConfig, ipAddress, subnet, gateway = parts[2:7]
    info(0, 'GetNetwork - configLock=%s ipConfig=%s ipAddress=%s subnet=%s gateway=%s' % (configLock, ipConfig, ipAddress, subnet, gateway))
    local_event_Network.emit({'configLock': configLock, 'ipConfig': ipConfig, 'ipAddress': ipAddress, 'subnet': subnet, 'gateway': gateway})

  tcp.request('get_NET,0:1', handleNetwork)

### Cable Types

# Infrared
#get_IR
#set_IR
#sendir
#stopir
#get_IRL
#stop_IRL
#recieveIR

# Serial
#get_SERIAL
#set_SERIAL

# Relay

RELAY_TYPES = ['SPST', 'SPDT', 'DPDT', 'Disabled']

RELAY_FOOTPRINT = {'SPST': 1, 'SPDT': 2, 'DPDT': 4, 'Disabled': 1}

def ParseRelayState(resp):
  resp = (resp or '').strip()

  if not resp.startswith('state,1:'): 
    # Relay module is always 1
    return

  parts = resp.split(',')

  if len(parts) != 3:
    warn(0, 'ParseRelayState - unexpected response [%s]' % resp)
    return

  port = parts[1].split(':')[1]
  e = lookup_local_event('Relay %s State' % port)

  if e != None:
    info(0, 'ParseRelayState %s - state [%s]' % (port, parts[2]))
    e.emit(int(parts[2]))

def SetupRelays():
  for port in range(1, 5):
    CreateRelay(port)

  HandleRelayType(1)

def CreateRelay(port):
  name = 'Relay %s Type' % port

  if lookup_local_event(name) == None:
    create_local_event(name, {'title': name, 'group': 'Relays', 'order': next_seq(), 'schema': {'type': 'string'}})

    def handleAction(arg):
      tcp.request('set_RELAY,1:%s,%s' % (port, arg), lambda resp: HandleRelayType(port, resp))

    create_local_action(name, handleAction, {'title': name, 'group': 'Relays', 'order': next_seq(), 'hint': 'Ports occupied by the target type must be Disabled first', 'schema': {'type': 'string', 'enum': RELAY_TYPES}})

  stateName = 'Relay %s State' % port

  if lookup_local_event(stateName) == None:
    create_local_event(stateName, {'title': stateName, 'group': 'Relays', 'order': next_seq(), 'schema': {'type': 'integer'}})

    def handleSetState(arg):
      tcp.send('setstate,1:%s,%s' % (port, arg)) # response in tcp_received

    create_local_action(stateName, handleSetState, {'title': stateName, 'group': 'Relays', 'order': next_seq(), 'hint': '0 = off/open; 1 = on/closed (or on1 for SPDT/DPDT); 2 = on2 (SPDT/DPDT only)', 'schema': {'type': 'integer'}})

def HandleRelayType(port, resp=None):
  if port > 4:
    return

  if resp == None: # not quired yet
    tcp.request('get_RELAY,1:%s' % port, lambda resp: HandleRelayType(port, resp))
    return

  parts = resp.split(',')
  relayType = parts[2] if len(parts) == 3 and parts[0] == 'RELAY' else None

  if relayType == None:
    warn(0, 'InitRelay %s - unexpected response [%s]' % (port, resp))
    return # e.g. a rejected manual set - nothing resolved, so nothing further to recheck

  info(0, 'InitRelay %s - type [%s]' % (port, relayType))
  lookup_local_event('Relay %s Type' % port).emit(relayType)

  footprint = RELAY_FOOTPRINT.get(relayType, 1)

  for p in range(port + 1, port + footprint): # ports absorbed into this one's footprint
    info(0, 'InitRelay %s - type [Unavailable]' % p)
    lookup_local_event('Relay %s Type' % p).emit('Unavailable')

  if relayType == 'Disabled' or relayType == 'Unavailable':
    HandleRelayType(port + footprint) # getstate always errors (ERR RO004) on a disabled/unavailable port
  else:
    tcp.request('getstate,1:%s,notify' % port, lambda resp: HandleRelayType(port + footprint))

# Sensors

def ParseSensorState(resp):
  resp = (resp or '').strip()

  if not resp.startswith('state,2:'): # sensor module is always 2
    return

  parts = resp.split(',')

  if len(parts) != 3:
    warn(0, 'ParseSensorState - unexpected response [%s]' % resp)
    return

  port = parts[1].split(':')[1]
  e = lookup_local_event('Sensor %s State' % port)

  if e != None:
    info(0, 'ParseSensorState %s - state [%s]' % (port, parts[2]))
    e.emit(int(parts[2]))

def ParseSensorNotify(resp):
  resp = (resp or '').strip()

  if not resp.startswith('SENSORNOTIFY,'):
    return

  parts = resp.split(',')

  if len(parts) not in (4, 5):
    warn(0, 'ParseSensorNotify - unexpected response [%s]' % resp)
    return

  port = parts[1].split(':')[1]
  e = lookup_local_event('Sensor %s Notify' % port)

  if e != None:
    notifyPort, interval = parts[2], parts[3]
    debounce = parts[4] if len(parts) == 5 else None
    info(0, 'ParseSensorNotify %s - notifyPort=%s interval=%s debounce=%s' % (port, notifyPort, interval, debounce))
    e.emit({'notifyPort': int(notifyPort), 'interval': int(interval), 'debounce': debounce})

def SetupSensors():

  def NextSensor(port):
    if port > 4:
      return
    InitSensor(port, lambda: NextSensor(port + 1))

  NextSensor(1)

def InitSensor(port, onDone):
  name = 'Sensor %s State' % port

  if lookup_local_event(name) == None:
    create_local_event(name, {'title': name, 'group': 'Sensors', 'order': next_seq(), 'schema': {'type': 'integer'}})

  notifyName = 'Sensor %s Notify' % port

  if lookup_local_event(notifyName) == None:
    notifySchema = {'type': 'object', 'properties': {
      'notifyPort': {'type': 'integer', 'order': 1, 'hint': '0 = disable all notifications; else UDP port to notify'},
      'interval':   {'type': 'integer', 'order': 2, 'hint': '0 = no periodic notifications; else interval in seconds'},
      'debounce':   {'type': 'string',  'order': 3, 'hint': 'minimum valid state duration, e.g. 500us, 100ms, 10s (default 100ms)'}}}

    create_local_event(notifyName, {'title': notifyName, 'group': 'Sensors', 'order': next_seq(), 'schema': notifySchema})

    def handleSetNotify(arg):
      cmd = 'set_SENSORNOTIFY,2:%s,%s,%s' % (port, arg.get('notifyPort', 0), arg.get('interval', 0))

      if arg.get('debounce'):
        cmd += ',%s' % arg['debounce']

      tcp.request(cmd, ParseSensorNotify)

    create_local_action(notifyName, handleSetNotify, {'title': notifyName, 'group': 'Sensors', 'order': next_seq(), 'schema': notifySchema})

  def handleQuery(resp):
    # response covered by tcp_received
    onDone() 
    
  tcp.request('getstate,2:%s,notify' % port, handleQuery)

### Status

local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})
local_event_Status = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'schema': {'type': 'object', 'properties': {
  'level':   {'type': 'integer', 'order': 1},
  'message': {'type': 'string',  'order': 2}}}})

timer_Status = Timer(lambda: StatusCheck.call(), 20, 10) # Every 20s after first 10s

global _lastReceive
_lastReceive = system_clock()

@local_action({'title': 'Poll', 'group': 'Status'})
def StatusCheck():

  now = date_now()
  sinceLastReceive = system_clock() - _lastReceive # millis

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

def FormatPeriod(date, as_instant=False):
  """Takes in a date object and returns the phrase to be displayed in the dashboard"""

  if date == None:
    return 'for unknown period'
    
  time_difference = (date_now().getMillis() - date.getMillis()) / 1000 / 60 # in mins

  if time_difference < 0:
    return 'never ever'
  elif time_difference == 0:
    return 'for <1 min' if not as_instant else '<1 min ago'
  elif time_difference < 60:
    return ('for <%s mins' if not as_instant else '<%s mins ago') % time_difference
  elif time_difference < 60*24:
    return ('since %s' if not as_instant else 'at %s') % date.toString('h:mm:ss a')
  else:
    return ('since %s' if not as_instant else 'at %s') % date.toString('E d-MMM h:mm:ss a')

### Logging

local_event_LogLevel = LocalEvent({'group': 'Debug', 'order': 100000 + next_seq(), 'desc': 'Use this to ramp up the logging (with indentation)', 'schema': {'type': 'integer'}})

@local_action({'group': 'Debug', 'title': '+', 'order': 100000 + next_seq() })
def increaseLogLevel():
  local_event_LogLevel.emit((local_event_LogLevel.getArg() or 0) + 1)

@local_action({'group': 'Debug', 'title': '-', 'order': 100000 + next_seq() })
def decreaseLogLevel():
  local_event_LogLevel.emit((local_event_LogLevel.getArg() or 0) - 1)

def info(level, msg):
  if local_event_LogLevel.getArg() >= level:
    console.info(('  ' * level) + msg)

def error(level, msg):
  if local_event_LogLevel.getArg() >= level:
    console.error(('  ' * level) + msg)

def warn(level, msg):
  if local_event_LogLevel.getArg() >= level:
    console.warn(('  ' * level) + msg)

def log(level, msg):
  if local_event_LogLevel.getArg() >= level:
    console.log(('  ' * level) + msg)