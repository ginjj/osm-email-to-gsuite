"""Test script to verify adult leaders' member emails are also captured."""
from osm_api import osm_calls

# Get all sections
sections = osm_calls.get_sections()
terms = osm_calls.get_terms(sections)

print("Checking adult leaders across all sections for member emails:\n")
print("="*80)

for section, term in zip(sections, terms):
    members = osm_calls.get_members(section.sectionid, term.termid)
    
    # Find adult leaders
    adult_leaders = [m for m in members if m.is_adult_leader]
    
    if adult_leaders:
        print(f"\n{section.sectionname}:")
        for leader in adult_leaders:
            print(f"\n  {leader.full_name} (age {leader.age_today})")
            print(f"    Member Email 1: {leader.member_email_1 or '(none)'}")
            print(f"    Member Email 2: {leader.member_email_2 or '(none)'}")
            print(f"    Contacts: {len(leader.contacts)}")
            all_emails = leader.get_contact_emails()
            print(f"    Total emails collected: {len(all_emails)}")
            for email in all_emails:
                print(f"      - {email}")

print("\n" + "="*80)
