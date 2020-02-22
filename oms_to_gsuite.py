import sys
import yaml
from datetime import date
from pprint import pprint 
from osm_api import osm_calls
from gsuite_sync import gam_groups


def main():
    get_email_config()
    print_sections(section_emails, 'Sections found in config file:', 'id', 'email')
    sections = osm_calls.get_sections()
    print_sections(sections, 'Sections found in OSM:', 'sectionid', 'sectionname')
    terms = osm_calls.get_terms(sections)
    # Add terms to sections list (both are in the same order).  
    for i in range(len(sections)):
        if sections[i]['sectionid'] == terms[i]['sectionid']:
            sections[i].update(terms[i])
        else:
            sys.exit('Error matching terms to sections')

       
    valid_sections = [section for section in sections if section['sectionid'] in {section_email['id'] for section_email in section_emails}]
    print_sections(valid_sections, 'Sections in both OSM and config file with current term start date:', 'sectionid', 'sectionname', 'startdate')

    for section in valid_sections:
        members = osm_calls.get_members(section['sectionid'], section['termid'])
        leaders, young_leaders, parents = (set() for i in range(3))
        
        for member in members:
            age = age_today(member['date_of_birth'])
            if member['patrol'] == 'Leaders':
                if age > 18:
                    leaders.add(member['email'])
                elif age <= 18:
                    young_leaders.add(member['email'])    
            else:
                parents.add(member['email'])
        
        for s in section_emails:
            if s['id'] == section['sectionid']:
                section_email = s['email']
                break

        #update groups
        gam_groups.gam_sync_group(section_email + 'leaders', leaders)
        gam_groups.gam_sync_group(section_email + 'youngleaders', young_leaders)
        gam_groups.gam_sync_group(section_email + 'parents', parents)


def age_today(iso_dob):
     born = date.fromisoformat(iso_dob)
     today = date.today()
     return(today.year - born.year - ((today.month, today.day) < (born.month, born.day)))


def print_sections(lst, title, key_1, key_2, key_3 = None):
    len_value_1 = max(len(max([d[key_1] for d in lst], key=len)),len(key_1))
    len_value_2 = max(len(max([d[key_2] for d in lst], key=len)),len(key_2))
    if key_3:
        len_value_3 = max(len(max([d[key_3] for d in lst], key=len)),len(key_2))

    print()
    print(title, len(lst))
    print(key_1.ljust(len_value_1),' ',
          key_2.ljust(len_value_2),' ',
          key_3.ljust(len_value_3) if key_3 else '')
    print('-' * len_value_1,' ',
          '-' * len_value_2,' ',
          '-' * len_value_3 if key_3 else '') 
    for dic in lst:
        print(dic[key_1].ljust(len_value_1),' ',
              dic[key_2].ljust(len_value_2),' ',
              dic[key_3].ljust(len_value_3) if key_3 else '')


def get_email_config():
    global section_emails
    with open('email_config.yaml', 'r') as stream:
        try:
            dictionary = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    section_emails = dictionary['sections']    

if __name__ == '__main__':
    main()