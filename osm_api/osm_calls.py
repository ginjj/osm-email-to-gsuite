import yaml
import requests
import re
from pprint import pprint 

# Get OSM API coniguration 
with open('osm_config.yaml', 'r') as stream:
    try:
        dictionary = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)
api_auth_values = dictionary['osm-api']
base_url = dictionary['base-url']


def get_sections():     # Get sections
    url_path = 'api.php?action=getUserRoles'
    user_roles_data = osm_post(url_path, api_auth_values)
    sections = []
    for section in user_roles_data:
        section_dict = { key: section[key] for key in (
            'sectionid',
            'sectionname',
            'section')}
        sections.append(section_dict)
    return sections


def get_terms(sections):    # Get latest started (i.e. 'past') term
    url_path = 'api.php?action=getTerms'
    terms_data = osm_post(url_path, api_auth_values)
    terms = []    
    for section in sections:
        started_terms = [n for n in terms_data[section['sectionid']] if n['past'] == True]
        current_term = max(started_terms, key=lambda x:x['startdate'])
        term_items = {key: current_term[key] for key in (
            'sectionid',
            'termid',
            'name',
            'startdate',
            'enddate')}
        terms.append(term_items)
    return terms

def get_all_terms(sections):    # Get all terms trial 11/2021
    url_path = 'api.php?action=getTerms'
    terms_data = osm_post(url_path, api_auth_values)
    terms = []    
    for section in sections:
        started_terms = [n for n in terms_data[section['sectionid']] if n['past'] == True]
        for term in started_terms:
            #current_term = max(started_terms, key=lambda x:x['startdate'])
            term_items = {key: term[key] for key in (
                'sectionid',
                'termid',
                'name',
                'startdate',
                'enddate')}
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
        #print(members_data['data'][member]['patrol'].ljust(20),members_data['data'][member]['patrol_and_role'])
        for custom_section in ['1','2']:
            custom_section_dict = members_data['data'][member]['custom_data'][custom_section]
            for email_field in ['12','14']:
                if email_regex.match(custom_section_dict[email_field]):
                    member_dict = { key: members_data['data'][member][key] for key in (
                        'date_of_birth',
                        'first_name',
                        'last_name',
                        'member_id',
                        'patrol',
                        'section_id',
                        'started',
                        'joined')}
                    member_dict.update({
                        'email_first_name':custom_section_dict['2'],
                        'email_last_name':custom_section_dict['3'],
                        'email':custom_section_dict[email_field]})
                    members.append(member_dict)
                elif custom_section_dict[email_field] != '':
                    print('WARNING! Rejected email:', custom_section_dict[email_field]) 
    return members


def get_members_row(section, term):    # Get members for a given section and term
    values = {'section_id': section, 'term_id': term}
    values.update(api_auth_values)
    url_path = 'ext/members/contact/grid/?action=getMembers'
    email_regex = re.compile(r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)')  
    members_data = osm_post(url_path, values)
    #pprint(members_data['data'])
    members=[]
    for member in members_data['data']:
        #print(members_data['data'][member]['patrol'].ljust(20),members_data['data'][member]['patrol_and_role'])
        member_dict = { key: members_data['data'][member][key] for key in (
            'date_of_birth', 
            'first_name',
            'last_name',
            'member_id',
            'patrol', 
            'section_id',
            'started',
            'joined')}
        for custom_section in ['1','2']:
            custom_section_dict = members_data['data'][member]['custom_data'][custom_section]
            member_dict.update({
                'contact_' + custom_section + '_first_name':custom_section_dict['2'],
                'contact_' + custom_section + '_last_name':custom_section_dict['3'],
                'contact_' + custom_section + '_email_1':custom_section_dict['12'],
                'contact_' + custom_section + '_email_2':custom_section_dict['14']})
        members.append(member_dict)
    return members


def get_attendance_structure(section, term, section_type):
    values = {'sectionid': section, 'termid': term, 'section': section_type, 'nototal':'true'}
    values.update(api_auth_values)
    url_path = 'ext/members/attendance/?action=structure'
    attendance_structure_data = osm_post(url_path, values) # Returns a list with two items for column names

    attendance_table_columns = [] 
    for attendance_structure_section in attendance_structure_data:
        for column in attendance_structure_section['rows']:
            current_column = column['field']
            attendance_table_columns.append(current_column)
    return attendance_table_columns

def get_attendance(section, term, section_type):
    values = {'sectionid': section, 'termid': term, 'section': section_type, 'nototal':'true'}
    values.update(api_auth_values)
    url_path = 'ext/members/attendance/?action=get'
    attendance_data = osm_post(url_path, values)
    return attendance_data

def osm_post(url_path, values):    # OSM API query via POST method
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(base_url + url_path, data=values, headers=headers)
        response.raise_for_status()
    except requests.RequestException:
        print('Error with OSM POST method')
        return None
    return response.json()