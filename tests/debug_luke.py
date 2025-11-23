"""Debug script to check Luke's member data structure."""
from osm_api import osm_calls
import json

# Get sections
sections = osm_calls.get_sections()
skidmore = [s for s in sections if 'skidmore' in s.sectionname.lower()][0]

print(f"Skidmore section: {skidmore.sectionname} (ID: {skidmore.sectionid})")

# Get terms first
terms = osm_calls.get_terms([skidmore])
print(f"Term: {terms[0].name} (ID: {terms[0].termid})")

# Get members using dict function to see raw API response
from osm_api.osm_calls import get_members_dict
members = get_members_dict(skidmore.sectionid, terms[0].termid)

print(f"\nTotal members: {len(members)}")

# Find Luke
for member in members:
    if 'luke' in member.get('first_name', '').lower() and 'spendlove' in member.get('last_name', '').lower():
        print(f"\n{'='*80}")
        print(f"LUKE SPENDLOVE FULL RECORD (ALL FIELDS):")
        print(f"{'='*80}")
        # Print all top-level fields first
        print("\nTop-level fields:")
        for key, value in member.items():
            if key != 'custom_data':
                print(f"  {key}: {value}")
        
        # Print custom_data if it exists
        if 'custom_data' in member:
            print("\nCustom Data (Contacts):")
            print(json.dumps(member['custom_data'], indent=2, default=str))
        break
