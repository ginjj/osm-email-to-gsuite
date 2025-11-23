"""Test script to verify Luke's member emails are captured."""
from osm_api import osm_calls

# Get sections
sections = osm_calls.get_sections()
skidmore = [s for s in sections if 'skidmore' in s.sectionname.lower()][0]

print(f"Skidmore section: {skidmore.sectionname} (ID: {skidmore.sectionid})")

# Get terms and members
terms = osm_calls.get_terms([skidmore])
members = osm_calls.get_members(skidmore.sectionid, terms[0].termid)

# Find Luke
for member in members:
    if 'luke' in member.first_name.lower() and 'spendlove' in member.last_name.lower():
        print(f"\n{'='*80}")
        print(f"Luke Spendlove (age {member.age_today})")
        print(f"{'='*80}")
        print(f"Patrol: {member.patrol}")
        print(f"Is Young Leader: {member.is_young_leader}")
        print(f"\nMember's own emails:")
        print(f"  Email 1: {member.member_email_1}")
        print(f"  Email 2: {member.member_email_2}")
        print(f"\nContacts: {len(member.contacts)}")
        for i, contact in enumerate(member.contacts, 1):
            print(f"  Contact {i}: {contact.first_name} {contact.last_name}")
            print(f"    Email 1: {contact.email_1}")
            print(f"    Email 2: {contact.email_2}")
        print(f"\nAll emails (combined):")
        for email in member.get_contact_emails():
            print(f"  - {email}")
        break
