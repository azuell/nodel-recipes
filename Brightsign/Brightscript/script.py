'''
**Brightsign** for use with Nodel Brightsign Plugin

`rev 4` rewite of original script by Troy Takac

Includes:

*

**REVISION HISTORY**

* 

'''

DEFAULT_SCRIPT_PORT     = 8081
DEFAULT_UDP_PORT        = 5000

param_playerConfig = Parameter({'title': 'Brightsign Config', 'schema': {'type': 'object', 'properties': {
            'ipAddress': {'title': 'IP Address', 'type': 'string', 'hint': 'IP Address', 'order': 1},
            'scriptPort': {'title': 'Script Port', 'type': 'string', 'hint': '%s' % DEFAULT_SCRIPT_PORT, 'order': 2},
            'udpPort': {'title': 'UDP Port', 'type': 'integer', 'hint': '%s' % DEFAULT_UDP_PORT, 'order': 3}}}})

param_disabled = Parameter({'schema': {'type': 'boolean'}, 'desc': 'Disables this node'})

local_event_Model = LocalEvent({'group': 'Information', 'order': next_seq(), 'schema': {'type': 'string'}})
local_event_Serial = LocalEvent({'group': 'Information', 'order': next_seq(), 'schema': {'type': 'string'}})
local_event_VideoMode = LocalEvent({'group': 'Information', 'order': next_seq(), 'schema': {'type': 'string'}})

local_event_Power = LocalEvent({'group': 'Power', 'order': next_seq(), 'schema': {'type': 'string', 'enum': ['On', 'Off']}, 'desc': 'Power State'})
local_event_DesiredPower = LocalEvent({'group': 'Power', 'order': next_seq(), 'schema': {'type': 'string', 'enum': ['On', 'Off']}, 'desc': 'Desired Power State'})

local_event_Volume = LocalEvent({'group': 'Volume', 'order': next_seq(), 'schema': {'type': 'string'}})
local_event_Mute = LocalEvent({'group': 'Volume', 'order': next_seq(),'schema': {'type': 'string', 'enum': ['On', 'Off']}, 'desc': 'Mute State'})
local_event_DesiredMute = LocalEvent({'group': 'Volume', 'order': next_seq(),'schema': {'type': 'string', 'enum': ['On', 'Off']}, 'desc': 'Desired Mute State'})  

local_event_Playback = LocalEvent({'group': 'Playback', 'order': next_seq(),'schema': {'type': 'string'}, 'desc': 'Playback State'})
local_event_DesiredPlayback = LocalEvent({'group': 'Playback', 'order': next_seq(),'schema': {'type': 'string'}, 'desc': 'Desired Playback State'})

import sys

def main():
  if param_disabled:
      return console.warn('Disabled! Nothing to do')
    
  if is_blank((param_playerConfig or {}).get('ipAddress')):
    return console.warn('IP address not specified!')
  
  
    
    # console.info('Polling will start in %ss' % _timer_sync.getDelay())
    # _timer_sync.start()
    # if is_blank(param_ipAddress):
    #     _timer_sync.stop()
    #     return console.warn('IP address not specified!')
    
    # console.info('Polling will start in %ss' % _timer_sync.getDelay())
    # _timer_sync.start()
    

# # Script Entrypoint
# def main(arg = None):
#   global ipAddress, scriptPort, udpPort, fullAddress
#   if is_blank((param_playerConfig or {}).get('ipAddress')):
#     console.error('No Address has been specified, nothing to do!')
#     return
#   else:
#     ipAddress = (param_playerConfig or {}).get('ipAddress')
#   scriptPort = (param_playerConfig or {}).get('scriptPort') or scriptPort
#   udpPort = (param_playerConfig or {}).get('udpPort') or udpPort

#   fullAddress = "http://%s:%s" % (ipAddress, scriptPort)

#   console.log("Brightsign script started.")

# udp = UDP()

# def SendUDP(message):
    
#     if (param_IP != None):
#         if (param_PORT != None):
#             destination = "%s:%s" % (param_IP, param_PORT)
#         else:
#             destination = "%s:%s" % (param_IP, DEFAULT_PORT)
#         udp.setDest(destination)
#         udp.send(message)
#         console.log("UDP to %s sent" % destination)
#     else:
#         console.error("IP Address empty")

### HTTP Communications

_busy = False

def call(command, forceLog=False, method=None, query=None, contentType=None, post=None, fullResponse=False):
    # Avoid simultaneous calls by tracking one at a time
    global _busy
    if _busy:
        return False
    _busy = True

    try:
        scriptPort = DEFAULT_SCRIPT_PORT if is_blank(param_playerConfig.get('scriptPort')) else param_playerConfig.get('scriptPort')
        url = 'http://%s:%s/%s' % (param_playerConfig.get('ipAddress'), scriptPort, command)

        if forceLog: console.info('req: url%s' % url)
        else: log(1, 'req: url%s' % url)

        try:
            timestamp = system_clock()
            # get_url(url, method=None, query=None, username=None, password=None, headers=None, contentType=None, post=None, connectTimeout=10, readTimeout=15, fullResponse=False)
            resp = get_url(url, method=method, query=query, contentType=None, post=post, connectTimeout=5, readTimeout=5, fullResponse=fullResponse)
        except:
            e = sys.exc_info()[1]   # Tuple order is excType, value, trace
            msg = 'get_url: failed (took %0.1f) with "%s"' % ((system_clock()-timestamp)/1000.0, e)

            if forceLog: console.warn(msg)
            else:       warn(1, msg)

            return False

        log(1, 'resp: %s' % resp)

        global _lastReceive
        _lastReceive = system_clock()

        return resp
    
    finally:
        _busy = False

@local_action({'title': 'test full resp'})
def test():
  resp = call('status', forceLog=True, method='GET', contentType='application/json', fullResponse=True)
  console.log(resp)

@local_action({'title': 'Get Info', 'order': next_seq()})
def status():
  resp = call('status', forceLog=True, method='GET', contentType='application/json')
  console.log(resp)
  status_decode = json_decode(resp)

  lookup_local_event('Model').emit(status_decode['model'])
  
  lookup_local_event('Serial').emit(status_decode['serialNumber'])
  lookup_local_event('VideoMode').emit(status_decode['videomode'])

  lookup_local_event('Volume').emit(status_decode['volume'])
  #muted: false

  #playing: true
  #sleep: false


### Status and Error Reporting

_lastReceive = 0

local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})

local_event_Status = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'schema': {'type': 'object', 'properties': {
  'level': {'type': 'integer', 'order': 1},
  'message': {'type': 'string', 'order': 2}}}})

def statusCheck():
  diff = (system_clock() - _lastReceive)/1000.0 # in secs

  if diff > status_check_interval:
    previous_contact_value = local_event_LastContactDetect.getArg()
    
    if previous_contact_value == None:
      message = 'Never seen'
    else:
      previous_contact = date_parse(previous_contact_value)
      message = 'Missing %s' % formatPeriod(previous_contact)
      local_event_Status.emit({'level': 2, 'message': message})
    
  else:
    local_event_LastContactDetect.emit(str(date_now()))
    local_event_Status.emit({'level': 0, 'message': 'OK'})

def formatPeriod(date, as_instant=False):
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
    
status_check_interval = 75

status_timer = Timer(statusCheck, status_check_interval)


### Logging

local_event_LogLevel = LocalEvent({'group': 'Debug', 'order': 10000+next_seq(), 'desc': 'Use this to ramp up the logging (with indentation)', 'schema': {'type': 'integer'}})

def warn(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.warn(('  ' * level) + msg)

def log(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.log(('  ' * level) + msg)



