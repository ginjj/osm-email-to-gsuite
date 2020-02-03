import os
import sys
import requests #https://2.python-requests.org//en/latest/user/quickstart/#json-response-content
import re
import yaml
import subprocess
from datetime import date
from pprint import pprint 


def main():
    get_config()
    print_sections(section_emails, 'Sections found in config file:', 'id', 'email')
    sections = get_sections()
    print_sections(sections, 'Sections found in OSM:', 'sectionid', 'sectionname')
    terms = get_terms(sections)
    # Add terms to sections list (both are in the same order).  
    for i in range(len(sections)):
        if sections[i]['sectionid'] == terms[i]['sectionid']:
            sections[i].update(terms[i])
        else:
            sys.exit('Error matching terms to sections')

       
    valid_sections = [section for section in sections if section['sectionid'] in {section_email['id'] for section_email in section_emails}]
    print_sections(valid_sections, 'Sections in both OSM and config file with current term start date:', 'sectionid', 'sectionname', 'startdate')

    for section in valid_sections:
        members = get_members(section['sectionid'], section['termid'])

        leaders, young_leaders, parents = (set() for i in range(3))

        for member in members:
            age = age_today(member['date_of_birth'])
            if member['patrol_and_role'] == 'Normal':
                parents.add(member['email'])
            elif age > 18:
                leaders.add(member['email'])
            elif age <= 18:
                young_leaders.add(member['email'])    

        for s in section_emails:
            if s['id'] == section['sectionid']:
                section_email = s['email']
                break

        #update groups
        gam_sync_group(section_email + 'leaders', leaders)
        gam_sync_group(section_email + 'youngleaders', young_leaders)
        gam_sync_group(section_email + 'parents', parents)


def age_today(iso_dob):
     born = date.fromisoformat(iso_dob)
     today = date.today()
     return(today.year - born.year - ((today.month, today.day) < (born.month, born.day)))


def gam_sync_group(group_name, email_address_set):
    # GAMADV-XTD3 setup for VS Code shell requires the follwing environment variables to be added to settings.json
    # 'GAMCFGDIR': 'C:\\GAMConfig', 'PATH': 'C:\\GAMADV-XTD3\\'
    # see https://github.com/taers232c/GAMADV-XTD3/wiki/How-to-Install-Advanced-GAM   
    # usage 'gam update group group_name sync 'email1 email2 ...'
    gam_command = 'gam update group ' + group_name + ' sync "' + ' '.join(email_address_set) +'"'
    print('Synchronising', group_name, 'group with', len(email_address_set), 'email addresses from OSM')
    try:
        subprocess.run(gam_command, cwd='C:\GAMWork', check=True)
    except subprocess.CalledProcessError as exc:                                                                                                   
        print('GAMADV-XTD3 error code:', exc.returncode, exc.output)
        sys.exit('Error when running sub-process GAMADV-XTD3 command')
    print('Sucessfully completed synchronising group')


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


def get_config():
    global api_auth_values
    global base_url
    global section_emails
    with open('config.yaml', 'r') as stream:
        try:
            dictionary = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    api_auth_values = dictionary['osm-api']
    base_url = dictionary['base-url']
    section_emails = dictionary['sections']    


def get_sections():     # Get sections
    url_path = 'api.php?action=getUserRoles'
    user_roles_data = osm_post(url_path, api_auth_values)
    sections = []
    for section in user_roles_data:
        section_dict = { key: section[key] for key in ('sectionid', 'sectionname', 'section')}
        sections.append(section_dict)
    return sections


def get_terms(sections):    # Get latest started (i.e. 'past') term
    url_path = 'api.php?action=getTerms'
    terms_data = osm_post(url_path, api_auth_values)
    terms = []    
    for section in sections:
        started_terms = [n for n in terms_data[section['sectionid']] if n['past'] == True]
        current_term = max(started_terms, key=lambda x:x['startdate'])
        term_items = {key: current_term[key] for key in ('sectionid','termid', 'name', 'startdate', 'enddate')}
        terms.append(term_items)
    return terms


def get_members(section, term):    # Get members for a given section and term
    values = {'section_id': section, 'term_id': term}
    values.update(api_auth_values)
    url_path = 'ext/members/contact/grid/?action=getMembers'
    email_regex = re.compile(r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)')  
    members_data = osm_post(url_path, values)
    #pprint(members_data['data'])
    members=[]
    for member in members_data['data']:
        for custom_section in ['1','2']:
            custom_section_dict = members_data['data'][member]['custom_data'][custom_section]
            for email_field in ['12','14']:
                if email_regex.match(custom_section_dict[email_field]):
                    member_dict = { key: members_data['data'][member][key] for key in ('age_years', 'date_of_birth', 'first_name', 'last_name', 'member_id', 'patrol', 'patrol_and_role', 'section_id')}
                    member_dict.update({
                        'email_first_name':custom_section_dict['2'],
                        'email_last_name':custom_section_dict['3'],
                        'email':custom_section_dict[email_field]
                    })
                    members.append(member_dict)
                elif custom_section_dict[email_field] != '':
                    print('WARNING! Rejected email:', custom_section_dict[email_field]) 
    return members


# OSM API query via POST method
def osm_post(url_path, values):
    base_url = 'https://www.onlinescoutmanager.co.uk/'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(base_url + url_path, data=values, headers=headers)
        response.raise_for_status()
    except requests.RequestException:
        print('Error with OSM POST method')
        return None
    return response.json()

'''
# OSM API query via GET method
def osm_get(url_path, values = None):
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(base_url + url_path, data=api_auth_values, headers=headers)
        response.raise_for_status()
    except requests.RequestException:
        print('Error with OSM GET method')
        return None
    return response.json() '''

if __name__ == '__main__':
    main()