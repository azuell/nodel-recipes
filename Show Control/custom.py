# custom.py - Show Control for OSC Agent
# Condense multiple OSC Agent node actions into one action with arguments and state, to be used on a Frontend node with < select > object

# REV 1 2026.05.04

# REVISION HISTORY
# * rev. 1: created

@after_main
def custom():
  console.info("Custom (OSC Show Control) has started!")
  
  if not is_empty(param_patterns):
    initLocalAction()
  
def initLocalAction():
  
  def handler(arg):
    lookup_local_action(arg).call()
    lookup_local_event('Show').emit(arg)

  create_local_action('Show', handler, {'title': 'Show', 'order': next_seq(), 'schema': {'type': 'string', 'enum': [pattern.get('label') for pattern in param_patterns]}})
  create_local_event('Show', {'title': 'Show', 'order': next_seq(), 'schema': {'type': 'string', 'enum': [pattern.get('label') for pattern in param_patterns]}})
