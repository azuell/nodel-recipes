'''
# Under Development
**Roller** API 

---

`REV 1 2026.02.13 azuell`

* Authentication with client information
* Grabs total number of bookings as an event

**MANUAL**

* [Roller API Documentation](https://docs.roller.app/docs/roller-api/)

**REVISION HISTORY**

* rev. 1: Initial upload

'''

AUTH_TIMEOUT          = 24 * 60 * 60 # seconds (24hrs)
STATUS_CHECK_INTERVAL = 75 # seconds
DELAY                 = 2 # seconds

_fullAddress = 'https://api.roller.app'

_lastReceive = 0

param_disabled = Parameter({'title': 'Disable this node', 'schema': {'type': 'boolean'}})

param_apiClient = Parameter({'title': 'API Client', 'schema': {'type': 'object', 'properties': {
  'client_id': {'title': 'API Client ID', 'type': 'string', 'order': 1},
  'client_secret': {'title': 'API Client Secret', 'type': 'string', 'order': 2}}}})

local_event_AuthToken = LocalEvent({'group': 'Authentication', 'schema': {'type': 'string'}})
local_event_AuthTokenExpires = LocalEvent({'group': 'Authentication', 'schema': {'type': 'string'}})

local_event_RollerBookingsToday = LocalEvent({'group': 'Bookings', 'schema': {'type': 'number'}})

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

  if param_apiClient is None:
    console.error('No client ID/secret information has been specified, cant authenticate!')
    return
  
  # console.info('Authentication timer starting now')
  # _timer_auth.start()

  # Start status polling
  _timer_status.start()

_timer_auth = Timer(lambda: GetAuthToken.call(), AUTH_TIMEOUT - 30, 10, stopped=True)
_timer_status = Timer(lambda: StatusCheck.call(), STATUS_CHECK_INTERVAL, 10, stopped=True) 

### HTTP Communications

_busy = False

def callURL(command, forceLog=False, method=None, query=None, headers=None, contentType=None, post=None):
  # Avoid simultaneous calls by tracking one at a time
  global _busy
  if _busy:
    return False
  _busy = True

  try:
    url = '%s%s' % (_fullAddress, command)

    if forceLog: console.info('req: url%s' % url)
    else: info(1, 'req: url%s' % url)

    # No access token if not required, or when authenticating
    if command != '/token':
      if not headers:
        headers = {}
      headers['Authorization'] = 'Bearer %s' % local_event_AuthToken.getArg()
      headers['Connection'] = 'close'

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

### Information and Authentication

@local_action({'title': 'Auth', 'group': 'Authentication'})
def GetAuthToken():
  req = {'client_id': param_apiClient.get('client_id'), 'client_secret': param_apiClient.get('client_secret')}
  resp = callURL('/token', method='POST', contentType='application/json', post=json_encode(req))
  result = json_decode(resp) 

  local_event_AuthToken.emit(result.get('access_token'))
  local_event_AuthTokenExpires.emit(result.get('expires_in'))
  _timer_auth.setInterval(result.get('expires_in'))

### Bookings

@local_action({'title': 'Get Bookings'})
def GetBookings():
  # GET /bookings
  console.log('Getting bookings for: %s' % str(date_now())[0:10])

  params = {'date': str(date_now())[0:10]}
  resp = callURL('/bookings', method='GET', contentType='application/json', query=params)
  result = json_decode(resp)

  bookings = result.get('bookings')

  local_event_RollerBookingsToday.emit(len(bookings))

### Products

@local_action({'title': 'Get Products'})
def GetProducts():
  # GET /data/products

  # Find total pages
  resp = callURL('/data/products', method='GET')
  result = json_decode(resp)
  totalPages = result.get('totalPages')

  # Find all published products
  publishedProducts = []
  for page in range(totalPages):
    page += 1  # Don't want 0-indexing
    for product in json_decode(callURL('/data/products?pageNumber=%s' % page, method='GET')).get('items'):
      if product.get('productStatus') == 'Published':
        publishedProducts.append(product)


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



