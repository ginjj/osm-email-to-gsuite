"""Check if any regular members (non-leaders) have member emails."""
from osm_api import osm_calls

# Get all sections
sections = osm_calls.get_sections()
terms = osm_calls.get_terms(sections)

print("Checking for member emails on regular members (non-leaders/non-YLs):\n")
print("="*80)

members_with_emails = []

for section, term in zip(sections, terms):
    members = osm_calls.get_members(section.sectionid, term.termid)
    
    # Find regular members (not leaders)
    regular_members = [m for m in members if not m.is_leader]
    
    for member in regular_members:
        if member.member_email_1 or member.member_email_2:
            members_with_emails.append({
                'section': section.sectionname,
                'name': member.full_name,
                'age': member.age_today,
                'patrol': member.patrol,
                'email1': member.member_email_1,
                'email2': member.member_email_2
            })

if members_with_emails:
    print(f"\nWARNING: Found {len(members_with_emails)} regular members with member emails:\n")
    for m in members_with_emails:
        print(f"Section: {m['section']}")
        print(f"  Name: {m['name']} (age {m['age']}, patrol: {m['patrol']})")
        print(f"  Email 1: {m['email1']}")
        print(f"  Email 2: {m['email2']}")
        print()
else:
    print("\nGOOD: No regular members have member emails set.")
    print("   Only leaders and young leaders have member emails.")

print("="*80)
