import sys
import yaml
import csv
from datetime import date, time
import time
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
            print('sections', type(sections[i]['sectionid']))
            sections[i].update(terms[i])
        else:
            sys.exit('Error matching terms to sections')

    valid_sections = [section for section in sections if section['sectionid'] in {section_email['id'] for section_email in section_emails}]
    print_sections(valid_sections, 'Sections in both OSM and config file with current term start date:', 'sectionid', 'sectionname', 'startdate')

    with open('osm_members_' + time.strftime("%Y-%m-%d-%H%M%S") + '.csv', 'w', newline='') as file:
        fieldnames = [
            'section_name',
            'member_id',
            'first_name',
            'last_name',
            'date_of_birth',
            'patrol',
            'joined',
            'started',
            'contact_1_first_name',
            'contact_1_last_name',
            'contact_1_email_1',
            'contact_1_email_2',
            'contact_2_first_name',
            'contact_2_last_name',
            'contact_2_email_1', 
            'contact_2_email_2']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for section in valid_sections:
            members = osm_calls.get_members_row(section['sectionid'], section['termid'])
            for member in members:
                section_name = {'section_name': next(item['email'] for item in section_emails if item['id'] == str(member['section_id']))}
                member.update(section_name)
                member.pop('section_id')

            writer.writerows(members)      


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