"""Debug script to inspect OSM member data structure."""
import yaml
from pprint import pprint
from osm_api import osm_calls

# Load config
with open('email_config.yaml', 'r') as f:
    email_config = yaml.safe_load(f)

# Get Smithies section (first in config)
section_id = email_config['sections'][0]['id']
print(f"Loading members for section ID: {section_id}")

# Get sections and terms
sections = osm_calls.get_sections()
terms = osm_calls.get_terms(sections)

# Find matching term
term_id = None
for section in sections:
    if section.sectionid == section_id:
        for term in terms:
            if term.sectionid == section_id:
                term_id = term.termid
                break
        break

print(f"Using term ID: {term_id}\n")

# Get raw member data
values = {'section_id': section_id, 'term_id': term_id}
values.update(osm_calls.api_auth_values)
url_path = 'ext/members/contact/grid/?action=getMembers'
members_data = osm_calls.osm_post(url_path, values)

# Print first member's full structure
if members_data and 'data' in members_data:
    first_member_id = list(members_data['data'].keys())[0]
    first_member = members_data['data'][first_member_id]
    
    print("="*80)
    print("FIRST MEMBER DATA STRUCTURE:")
    print("="*80)
    pprint(first_member)
    
    print("\n" + "="*80)
    print("AVAILABLE KEYS:")
    print("="*80)
    for key in sorted(first_member.keys()):
        print(f"  {key}: {type(first_member[key]).__name__}")
    
    # Look for young leaders specifically
    print("\n" + "="*80)
    print("CHECKING FOR YOUNG LEADERS:")
    print("="*80)
    for member_id, member in members_data['data'].items():
        # Check various fields that might indicate young leader
        patrol = member.get('patrol', '')
        patrol_and_role = member.get('patrol_and_role', '')
        
        if 'leader' in patrol.lower() or 'leader' in patrol_and_role.lower():
            print(f"\n{member['first_name']} {member['last_name']}:")
            print(f"  patrol: {patrol}")
            print(f"  patrol_and_role: {patrol_and_role}")
            print(f"  age: {member.get('age', 'N/A')}")
else:
    print("No member data returned!")
