"""Folded open stand envelopes and the four lead-in configurations."""
from stand10 import safety as safety_profile,design as lead_design

def lead_layout(a):
    result=lead_design(a)
    return [x['points'] for x in result['paths'] if x['key']!='ALIGN'],[(n['point'],n['direction']) for n in result['numbers']]
