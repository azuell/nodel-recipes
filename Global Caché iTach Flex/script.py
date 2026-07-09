# coding=utf-8
u"Global Caché iTach Flex Ethernet"

# Handy reference for model iTachFlexEthernetPoe (via AMX beacon)
# * https://www.globalcache.com/products/itach/ip2ccspecs/
# * https://www.globalcache.com/files/docs/API-iTach.pdf
# * https://www.globalcache.com/files/releases/flex-16/API-Flex_TCP_1.6.pdf

''''''

# <!-- parameters

param_disabled = Parameter({'schema': {'type': 'boolean'}})

param_ipAddress = Parameter({'schema': {'type': 'string' }})

param_relays = Parameter({'schema': {'type': 'array', 'items': {'type': 'object', 'properties': {
                              'port': {'type': 'integer', 'hint': '(1 to 4)', 'order': 1},
                              'label': {'type': 'string', 'order': 2}}}}})

param_sensors = Parameter({'schema': {'type': 'array', 'items': {'type': 'object', 'properties': {
                              'port': {'type': 'integer', 'hint': '(1 to 4)', 'order': 1},
                              'label': {'type': 'string', 'order': 2},
                              'invert': {'type': 'boolean', 'order': 3}}}}})

# -->

CONTROL_PORT = 4998

# <!-- main entry-point

_portInfo_byNum = { } # uses 'R' or 'S' prefix in keys (relay vs sensor)


def main():
  if param_disabled:
    console.warn('Node is disabled; will not connect TCP')
    return
  
  if not param_ipAddress:
    console.warn('IP address has not been specified')
    return

  dest = '%s:%s' % (param_ipAddress, CONTROL_PORT)

  console.info('Will connect to TCP %s' % dest)
  
  # prepare label lookup
  for item in param_relays or EMPTY:
    _portInfo_byNum['R%s' % item['port']] = item
  for item in param_sensors or EMPTY:
    _portInfo_byNum['S%s' % item['port']] = item
  
  for p in [1, 2, 3, 4]:
    initRelay(p)
    
  for p in [1, 2, 3, 4]:
    initSensor(p)

  tcp.setDest(dest)

# -->

_pollers = list()

def initRelay(p):
  info = _portInfo_byNum.get('R%s' % p) or EMPTY
  label = info.get('label')

  e = create_local_event('Relay %s' % p, {'title': '"%s" (%s' % (label, p) if label else 'Relay %s' % p, 'group': 'Relays', 'order': next_seq(), 'schema': {'type': 'boolean'}})
  
  def handle_action(arg):
    # TODO
    pass
  
  a = create_local_action('Relay %s' % p, handle_action, {'title': '"%s" (%s' % (label, p) if label else 'Relay %s' % p, 'group': 'Relays', 'order': next_seq(), 'schema': {'type': 'boolean'}})
  
def initSensor(p):
  info = _portInfo_byNum.get('S%s' % p) or EMPTY
  label = info.get('label')
  invert = info.get('invert') or False
  
  e = create_local_event('Sensor %s' % p, {'title': '"%s" (%s' % (label, p) if label else 'Sensor %s' % p, 'group': 'Sensors', 'order': next_seq(), 'schema': {'type': 'boolean'}})
  
  def poll():
    def handle_resp(resp):
      # e.g. > state,1:1,0 or       contacts-closed or voltage below threshold
      #      > state,1:1,1          contacts-open or voltage above threshold
      if 'ERR' in resp:
        console.warn('Got error polling port %s - [%s]' % (p, resp))
        return
      
      parts = resp.split(',')
      closed = parts[2] == '0' # last part has state
      e.emitIfDifferent(closed if not invert else not closed)
    
    tcp.request('getstate,2:%s' % p, handle_resp)
  
  # register poller
  _pollers.append(Timer(poll, 0.5, 2, stopped=True))
  

# <!-- TCP: this section demonstrates some TCP functions

def tcp_connected():
  console.info('tcp_connected')
  
  [poller.start() for poller in _pollers] # start all

def tcp_disconnected():
  console.warn('tcp_disconnected')
  
  [poller.stop() for poller in _pollers] # stop all

def tcp_timeout():
  console.warn('timeout')

def tcp_sent(data):
  log(1, "tcp_sent [%s]" % data)

def tcp_received(data):
  log(1, "tcp_received [%s]" % data)

  global _lastReceive # for status monitoring
  _lastReceive = system_clock()

tcp = TCP(connected=tcp_connected, 
          disconnected=tcp_disconnected, 
          sent=tcp_sent,
          received=tcp_received,
          timeout=tcp_timeout, 
          sendDelimiters='\r', 
          receiveDelimiters='\r\n')

# <!-- status

local_event_Status = LocalEvent({'group': 'Status', 'order': 9990, "schema": {'type': 'object', 'properties': {
                                   'level':   {'type': 'integer', 'order': 1},
                                   'message': {'type': 'string', 'order': 2}}}})

_lastReceive = 0 # last valid comms, system_clock() based

# roughly, the last contact  
local_event_LastContactDetect = LocalEvent({'group': 'Status', 'title': 'Last contact detect', 'schema': {'type': 'string'}})
  
def statusCheck():
  diff = (system_clock() - _lastReceive)/1000.0 # (in secs)
  now = date_now()
  
  if diff > status_check_interval+15:
    previousContactValue = local_event_LastContactDetect.getArg()
    
    if previousContactValue == None: message = 'Never seen'
    else:
      previousContact = date_parse(previousContactValue)
      message = 'Missing %s' % formatPeriod(previousContact)
      
    local_event_Status.emit({'level': 2, 'message': message})
    return
    
  local_event_Status.emit({'level': 0, 'message': 'OK'})
  
  local_event_LastContactDetect.emit(str(now))
  
status_check_interval = 75
timer_statusCheck = Timer(statusCheck, status_check_interval)

def formatPeriod(dateObj):
  if dateObj == None:      return 'for unknown period'
  
  now = date_now()
  diff = (now.getMillis() - dateObj.getMillis()) / 1000 / 60 # in mins
  
  if diff == 0:             return 'for <1 min'
  elif diff < 60:           return 'for <%s mins' % diff
  elif diff < 60*24:        return 'since %s' % dateObj.toString('h:mm:ss a')
  else:                     return 'since %s' % dateObj.toString('E d-MMM h:mm:ss a')
  
# status -->

# <!-- logging

local_event_LogLevel = LocalEvent({'group': 'Debug', 'order': 10000+next_seq(), 'desc': 'Use this to ramp up the logging (with indentation)',  
                                   'schema': {'type': 'integer'}})

def warn(level, msg):
  if local_event_LogLevel.getArg() >= level:
    console.warn(('  ' * level) + msg)

def log(level, msg):
  if local_event_LogLevel.getArg() >= level:
    console.log(('  ' * level) + msg)

# --!>
