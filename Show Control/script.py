'''
**Show Control** 

Use case: condense multiple OSC Agent node actions into one action with arguments and state, to be used on a Frontend node with < select > object

`REV 1.1 2026.04.21`

**REVISION HISTORY**

* rev. 1.1: rename to 'name' in parameter properties
* rev. 1: created
'''

param_states = Parameter({'title': 'Show States', 'order': next_seq(), 'schema': {'type': 'array', 'items': {
  'type': 'object', 'title': 'State', 'properties': {
    'name': {'type': 'string', 'hint': 'Standard'}}}}})

param_node = Parameter({'title': 'Suggested Node', 'schema': {'type': 'string', 'hint': 'OSC Client'}})

def main():
  console.info("Recipe has started!")
  
  if not is_empty(param_states):
    initRemoteActions()
    initLocalAction()
  
def initLocalAction():
  
  def handler(arg):
    lookup_remote_action(arg).call()
    lookup_local_event('Show').emit(arg)

  create_local_action('Show', handler, {'title': 'Show', 'order': next_seq(), 'schema': {'type': 'string', 'enum': [show.get('name') for show in param_states]}})
  create_local_event('Show', {'title': 'Show', 'order': next_seq(), 'schema': {'type': 'string', 'enum': [show.get('name') for show in param_states]}})

def initRemoteActions():
  for show in param_states:
    create_remote_action(show.get('name'), suggestedNode=param_node, suggestedAction=show.get('name'))
