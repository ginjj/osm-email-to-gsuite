################################################################################################
# 
#  API Calls:
#  POST https://www.onlinescoutmanager.co.uk/api.php?action=getUserRoles with auth
#  POST https://www.onlinescoutmanager.co.uk/api.php?action=getSectionConfig
#  POST https://www.onlinescoutmanager.co.uk/api.php?action=getTerms
#  POST https://www.onlinescoutmanager.co.uk/api.php?action=getNotepads
#   




import os
import requests #  https://2.python-requests.org//en/latest/user/quickstart/#json-response-content
import urllib.parse
from pprint import pprint #  Pretty print

# Global variables
# Attempt to get API credentials fromm environment vaiables
try:
    api_auth_values = {'apiid': os.environ.get('OSM_API_ID'),
                      'token': os.environ.get('OSM_API_TOKEN'), 
                      'userid': os.environ.get('OSM_API_USERID'),
                      'secret': os.environ.get('OSM_API_SECRET')}
except:
    print("Error getting API keys and credentials from Environment variables")
    sys.exit(1)


def main():
    sections = get_sections()
    terms = get_terms(sections)
    for i in range(len(sections)):
        if sections[i]['sectionid'] == terms[i]['sectionid']:
            sections[i].update(terms[i])

    members = get_members(sections[0]['sectionid'], sections[0]['termid'])
    pprint(sections)
    pprint(terms)
    #pprint(members)



def get_sections():     # Get sections
    url_path = 'api.php?action=getUserRoles'
    user_roles_data = osm_post(url_path, api_auth_values)
    sections = []
    for section in user_roles_data:
        section_dict = { key: section[key] for key in ('sectionid', 'sectionname', 'section')}
        sections.append(section_dict)
    return sections


def get_terms(sections):    # Get latest terms
    url_path = 'api.php?action=getTerms'
    terms_data = osm_post(url_path, api_auth_values)
    terms = []    
    for section in sections:
        started_terms = [n for n in terms_data[section['sectionid']] if n['past'] == True]
        current_term = max(started_terms, key=lambda x:x['startdate'])
        term_items = {key: current_term[key] for key in ('sectionid','termid', 'name', 'startdate', 'enddate')}
        terms.append(term_items)
    return terms
    
def get_members(section, term):   #https://www.onlinescoutmanager.co.uk/ext/members/contact/grid/?action=getMembers   section_id: 12783 term_id: 364630
    values = {'section_id': section, 'term_id': term}
    values.update(api_auth_values)
    url_path = 'ext/members/contact/grid/?action=getMembers'
    members_data = osm_post(url_path, values)
    members=[]
    for member in members_data['data']:
        for custom_section in ['1','2','3']:
            custom_section_dict = members_data['data'][member]['custom_data'][custom_section]
            if {custom_section_dict['12']} !={''}:
                member_dict = { key: members_data['data'][member][key] for key in ('age_years', 'date_of_birth', 'first_name', 'last_name', 'member_id', 'patrol', 'patrol_and_role', 'section_id')}
                member_dict.update({
                    'email_first_name':custom_section_dict['2'],
                    'email_last_name':custom_section_dict['3'],
                    'email':custom_section_dict['12']
                })
                members.append(member_dict)
    return members


# OSM API query via GET method
def osm_get(url_path, values = None):
    base_url = 'https://www.onlinescoutmanager.co.uk/'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(base_url + url_path, data=auth, headers=headers)
        response.raise_for_status()
    except requests.RequestException:
        print("Error with OSM GET method")
        return None
    return response.json()


# OSM API query via POST method
def osm_post(url_path, values):
    base_url = 'https://www.onlinescoutmanager.co.uk/'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(base_url + url_path, data=values, headers=headers)
        response.raise_for_status()
    except requests.RequestException:
        print("Error with OSM POST method")
        return None
    return response.json()


if __name__ == "__main__":
    main()