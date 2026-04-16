'''
**Supabase** API (For 'Warne: Treasures of a Legend')

---

`REV 1 2026.02.23 azuell`

* Grabs list of show times ever two hours for today and creates an event for use with a Calendar node

**MANUAL**

* Organisation > Integrations > Data API for generated API docs for your database
* [SQL to REST API Translator](https://supabase.com/docs/guides/api/sql-to-rest)

**REVISION HISTORY**

* rev. 1: Initial upload

'''

STATUS_CHECK_INTERVAL = 75 # seconds
TIMES_CHECK_INTERVAL = 2 * 60 * 60 # 2hrs in seconds

_lastReceive = 0

param_disabled = Parameter({'title': 'Disable this node', 'schema': {'type': 'boolean'}})

param_url = Parameter({'title': 'Project URL', 'schema': {'type': 'string'}})

param_apikey = LocalEvent({'title': 'Secret API Key', 'group': 'Authentication', 'schema': {'type': 'string'}})

local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})
local_event_Status = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'schema': {'type': 'object', 'properties': {
        'level': {'type': 'integer', 'order': 1},
        'message': {'type': 'string', 'order': 2}}}})

def main():
  console.info('Recipe has started!')

@after_main
def start():
  # Disable node
  if param_disabled:
    console.error('Node is disabled. Doing nothing.')
    return

  if param_url is None:
    console.error('No URL information has been specified, cant do anything!')
    return
  
  if param_apikey is None:
    console.error('No auth token given, cant authenticate!')
    return

  # Start status and times polling
  _timer_status.start()
  _timer_times.start()

_timer_status = Timer(lambda: StatusCheck.call(), STATUS_CHECK_INTERVAL, 10, stopped=True) 
_timer_times = Timer(lambda: GetTimes.call(), TIMES_CHECK_INTERVAL, 10, stopped=True) 

### HTTP Communications

_busy = False

def callURL(command, forceLog=False, method=None, query=None, headers=None, contentType=None, post=None):
  # Avoid simultaneous calls by tracking one at a time
  global _busy
  if _busy:
    return False
  _busy = True

  try:
    url = '%s%s' % (param_url, command)

    if forceLog: console.info('req: url%s' % url)
    else: info(1, 'req: url%s' % url)

    if not headers:
      headers = {}
    headers['apikey'] = '%s' % param_apikey
    headers['Authorization'] = 'Bearer %s' % param_apikey

    try:
      timestamp = system_clock()
      # get_url(url, method=None, query=None, username=None, password=None, headers=None, contentType=None, post=None, connectTimeout=10, readTimeout=15, fullResponse=False)
      resp = get_url(url, method=method, query=query, headers=headers, contentType=contentType, post=post, fullResponse=True)

      if not(resp.statusCode >= 200 and resp.statusCode < 300):  # 200 codes are success
        raise Exception(str(resp.statusCode) + " Error: " + str(resp.reasonPhrase))

    except Exception, e:
      msg = 'get_url: failed (took %0.1f) with "%s"' % ((system_clock() - timestamp) / 1000.0, e)

      if forceLog: console.warn(msg)
      else:        warn(1, msg)

      return False
      
    log(1, 'resp: %s' % resp.content)

    global _lastReceive
    _lastReceive = system_clock()

    return resp.content
    
  finally:
    _busy = False

### Import Show Times

from org.nodel.reflection import Serialisation
from org.nodel.json import JSONArray

def jsonDecodeByArray(arrayString):
  return Serialisation.coerce(None, JSONArray(arrayString))

ITEM_SCHEMA = { 'type': 'object', 'title': '...', 'properties': {
                      'title': {'type': 'string', 'order': 1},
                      'start': {'type': 'string', 'order': 2},
                      'end': {'type': 'string', 'order': 3},
                      'member': {'type': 'string', 'order': 4},
                      'signal': {'type': 'string', 'order': 5},
                      'state': {'type': 'string', 'order': 6}
}}

local_event_WarneItems = LocalEvent({'title': 'Warne Items', 'schema': {'type': 'array', 'title': 'Warne Today', 'items': ITEM_SCHEMA}})
      
def getStartOfDay(instant):
  return date_at(instant.getYear(), instant.getMonthOfYear(), instant.getDayOfMonth(), 0, 0, 0, 0)

def listTimes(timeMin, timeMax):
  params = ('?select=starts_at&starts_at=gt.%s&starts_at=lt.%s&order=starts_at.asc' % (timeMin, timeMax)).replace('+', '%2B')
  resp = callURL('/rest/v1/sessions_with_availability%s' % params, method='GET', contentType='application/json')
  result = jsonDecodeByArray(resp)

  items = list()
  for obj in result:
    startInstant = date_instant(date_parse(obj.get('starts_at')).getMillis())  # Convert into local timezone for display convenience

    item = {'title': 'Warne', 
            'start': str(startInstant),
            'end': str(startInstant),
            'member': None,
            'signal': None,
            'state': None}
    
    items.append(item)

  info(0, 'Updating WarneItems')
  local_event_WarneItems.emit(items)

  return items

@local_action({'title': 'Fetch Todays Times'})
def GetTimes():
  day_start = getStartOfDay(date_now())
  items = listTimes(day_start, day_start.plusDays(1))

### Status

@local_action({'title': 'Poll', 'group': 'Status'})
def StatusCheck():
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