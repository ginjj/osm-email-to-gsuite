"""Debug script to find Luke's member email in custom fields."""
from osm_api.osm_calls import osm_post, api_auth_values
import json

# Get Skidmore section members with full data
values = {'section_id': '12049', 'term_id': '865913'}
values.update(api_auth_values)
url_path = 'ext/members/contact/grid/?action=getMembers'

response = osm_post(url_path, values)

print(f"Response keys: {response.keys()}")
print(f"\nMeta data:")
print(json.dumps(response.get('meta', {}), indent=2))

# Find Luke in the data
if 'data' in response:
    for member_id, member_data in response['data'].items():
        if 'luke' in member_data.get('first_name', '').lower():
            print(f"\n{'='*80}")
            print(f"LUKE'S FULL DATA INCLUDING CUSTOM_DATA:")
            print(f"{'='*80}")
            print(json.dumps(member_data, indent=2, default=str))
            break
