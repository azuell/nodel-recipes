'''
Alcorn McBride **8 TraXX** Eight Independent MP3 Players

---

`REV 2 2026.07.08 azuell`

* Sends commands via RS232C Serial Control
* Use '*' to target all channels

**MANUAL**

* [User's Guide](https://alcorn.com/wp-content/uploads/2016/04/man_8traxx.pdf)

**REVISION HISTORY**

* _rev. 2: Update for sharing_
* _rev. 1: Initial release_
'''

STATUS_CHECK_INTERVAL = 30 #s

CHANNELS = ['1', '2', '3', '4', '5', '6', '7', '8', '*'] # '*' for All Channels

ERROR_CODES = {'E00': 'Communication Error',
                'E04': 'Feature Not Available Yet',
                'E11': 'Media Not Present',
                'E12': 'Search Error',
                'E20': 'Format Error'}

param_ipAddress = Parameter({'schema': {'type': 'string', 'hint': 'will override bindings'}})
param_Port = Parameter({'schema': {'type': 'string', 'hint': 'will override bindings'}})

local_event_IPAddress = LocalEvent({'group': 'Network Info', 'order': 1, 'schema': {'type': 'string'}})
local_event_Port = LocalEvent({'group': 'Network Info', 'order': 2, 'schema': {'type': 'integer'}})

local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})
local_event_Status = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'schema': {'type': 'object', 'properties': {
  'level':   {'type': 'integer', 'order': 1},
  'message': {'type': 'string',  'order': 2}}}})

def remote_event_IPAddress(arg):
  if arg and same_value(arg, local_event_IPAddress.getArg()):
    return
  local_event_IPAddress.emit(arg)
  SetupTCP()

def remote_event_Port(arg):
  if arg and same_value(arg, local_event_Port.getArg()):
    return
  local_event_Port.emit(arg)
  SetupTCP()

### TCP

def tcp_connected():
  info(0, 'tcp_connected')

def tcp_disconnected():
  warn(0, 'tcp_disconnected')

def tcp_timeout():
  log(0, 'tcp_timeout')

def tcp_sent(data):
  log(2, 'tcp_sent [%s]' % data)

def tcp_received(data):
  log(2, 'tcp_received [%s]' % data)

  global _lastReceive
  _lastReceive = system_clock() # Any response is proof of presence

  ParseResponse(data)

tcp = TCP(connected=tcp_connected, 
          disconnected=tcp_disconnected, 
          sent=tcp_sent,
          received=tcp_received,
          timeout=tcp_timeout, 
          sendDelimiters='\r', # From docs: uses carriage return <CR> as send delimeter (\r)
          receiveDelimiters='\r\n')

### Main

def main():
  info(0, 'Started!')

@after_main
def SetupTCP():
  newDest = None
  
  if param_ipAddress and param_Port:
    newDest = '%s:%s' % (param_ipAddress, param_Port)
    info(0, 'Setting dest from params [%s]' % newDest)
    
  elif local_event_IPAddress.getArg() and local_event_Port.getArg():
    newDest = '%s:%s' % (local_event_IPAddress.getArg(), local_event_Port.getArg())
    info(0, 'Setting dest from binding [%s]' % newDest)
    
  else:
    warn(0, 'IP params or IP binding not specified!')
    return
  
  tcp.setDest(newDest)

### Play File to Channel

@local_action({'group': 'Operations', 'order': next_seq(), 
                'schema': {'type': 'object', 'properties': {
                'Channel': {'type': 'string', 'enum': CHANNELS, 'desc': 'channel number', 'order': 1},
                'Sound': {'type': 'integer', 'desc': 'sound number', 'order': 2}}}})
def PlayFileToChannel(arg):
  channel = arg.get('Channel') or '*'
  sound = arg.get('Sound')
  
  if sound: cmd = '%s%sPL' % (sound, channel)
  else:     cmd = '%sPL' % (channel)
    
  log(1, 'PlayFile: cmd [%s]' % cmd)

  tcp.send(cmd)

### Loop Play

@local_action({'group': 'Operations', 'order': next_seq(), 
                'schema': {'type': 'object', 'properties': {
                'Channel': {'type': 'string', 'enum': CHANNELS, 'desc': 'channel number', 'order': 1},
                'Sound': {'type': 'integer', 'desc': 'sound number', 'order': 2}}}})
def LoopPlayToChannel(arg):
  channel = arg.get('Channel') or '*'
  sound = arg.get('Sound')
  
  if sound: cmd = '%s%sLP' % (sound, channel)
  else:     cmd = '%sLP' % (channel)
    
  log(1, 'LoopPlay: cmd [%s]' % cmd)

  tcp.send(cmd)

### Assign Sound

@local_action({'group': 'Operations', 'order': next_seq(), 
                'schema': {'type': 'object', 'properties': {
                'Channel': {'type': 'string', 'enum': CHANNELS, 'desc': 'channel number', 'order': 1},
                'Sound': {'type': 'integer', 'desc': 'sound number', 'order': 2}}}})
def AssignSoundToChannel(arg):
  channel = arg.get('Channel') or '*'
  sound = arg.get('Sound')
  
  if sound: cmd = '%s%sSE' % (sound, channel)
  else:     cmd = '%sSE' % (channel)
    
  log(1, 'AssignSound: cmd [%s]' % cmd)

  tcp.send(cmd)

### Reset Channel

@local_action({'group': 'Operations', 'order': next_seq(), 
                'schema': {'type': 'object', 'properties': {
                'Channel': {'type': 'string', 'enum': CHANNELS, 'desc': 'channel number', 'order': 1}}}})
def ResetChannel(arg):
  channel = arg or '*'
  
  cmd = '%sRJ' % channel
    
  log(1, 'ResetChannel: cmd [%s]' % cmd)

  tcp.send(cmd)

#Mute/UnMute Channel

@local_action({'group': 'Operations', 'order': next_seq(), 
                'schema': {'type': 'object', 'properties': {
                'Channel': {'type': 'string', 'enum': CHANNELS, 'desc': 'channel number', 'order': 1},
                'Mute': {'type': 'string', 'enum': ['Mute', 'Unmute'], 'desc': 'sound number', 'order': 2}}}})
def MuteChannel(arg):
  channel = arg.get('Channel') or '*'
  mute = arg.get('Mute')
    
  # 0 for mute, 1 for unmute
  if mute == 'Mute':  cmd = '0%sAD' % channel
  else:               cmd = '1%sAD' % channel
    
  log(1, 'MuteChannel: cmd [%s] (%s)' % (cmd, mute))

  tcp.send(cmd)

#Keylock Control

@local_action({'group': 'Operations', 'order': next_seq(), 
                'schema': {'type': 'object', 'properties': {
                'State': {'type': 'string', 'enum': ['Enable', 'Disable'], 'order': 1}}}})
def KeylockControl(arg):
  state = arg.get('State')

  # 0 for disable, 1 for enable
  cmd = '0KL' if state == 'Disable' else '1KL'

  log(1, 'KeylockControl: cmd [%s] (%s)' % (cmd, state))

  tcp.send(cmd)

### Version Request

local_event_Version = LocalEvent({'group': 'Info', 'order': next_seq(), 'schema': {'type': 'string'}})

@local_action({'group': 'Info', 'order': next_seq()})
def PollVersion():
  # [?V] -> [Alcorn McBride 8TraXX V2.1]
  def resp_handler(resp):
    log(resp, 0)
    if not resp.startswith('Alcorn McBride 8TraXX'):
      warn(0, 'Bad resp to version request')
      return

    local_event_Version.emit(resp[resp.lower().find('v'):])
    
  tcp.request('?V', resp_handler)

### Error Codes

local_event_LastError = LocalEvent({'group': 'Status', 'order': next_seq(), 'title': 'Last error', 'schema': {'type': 'string'}})

def IsErrorCode(data):
  return len(data) == 3 and data[0] == 'E' and data[1:].isdigit()

def ParseErrorResponse(data):
  message = ERROR_CODES.get(data, 'Unknown error code')
  warn(0, 'error response [%s] %s' % (data, message))
  local_event_LastError.emit('%s (%s)' % (message, data))

def ParseResponse(data):
  if IsErrorCode(data):
    ParseErrorResponse(data)

### Status

timer_Status = Timer(lambda: StatusCheck.call(), 20, 10) # Every 20s after first 10s

global _lastReceive
_lastReceive = system_clock()

@local_action({'title': 'Poll', 'group': 'Status'})
def StatusCheck():
  PollVersion.call()

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
