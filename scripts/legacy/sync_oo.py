"""
Main synchronization script using object-oriented architecture.
Pulls member data from OSM and syncs to Google Workspace groups.
"""
import sys
import yaml
from typing import List, Dict
from osm_api import osm_calls
from osm_api.models import Section
from gsuite_sync import gam_groups


def main():
    """Main execution function."""
    # Load configuration
    section_configs = load_email_config()
    print_config_summary(section_configs)
    
    # Fetch sections from OSM
    sections = osm_calls.get_sections()
    print_sections_summary(sections, "Sections found in OSM")
    
    # Fetch terms for each section
    terms = osm_calls.get_terms(sections)
    
    # Attach terms to sections
    attach_terms_to_sections(sections, terms)
    
    # Filter sections that are in both OSM and config
    valid_sections = filter_valid_sections(sections, section_configs)
    print_sections_with_terms(valid_sections, "Valid sections with current terms")
    
    # Load members for each section and sync to Google groups
    for section in valid_sections:
        process_section(section)


def load_email_config() -> List[Dict]:
    """Load email configuration from YAML file."""
    with open('email_config.yaml', 'r') as stream:
        try:
            config_data = yaml.safe_load(stream)
            return config_data['sections']
        except yaml.YAMLError as exc:
            print(f'Error loading email_config.yaml: {exc}')
            sys.exit(1)


def attach_terms_to_sections(sections: List[Section], terms: List):
    """Attach term objects to corresponding sections."""
    for i, section in enumerate(sections):
        if i < len(terms) and section.sectionid == terms[i].sectionid:
            section.current_term = terms[i]
        else:
            sys.exit(f'Error matching terms to sections for {section.sectionname}')


def filter_valid_sections(sections: List[Section], configs: List[Dict]) -> List[Section]:
    """Filter sections that exist in both OSM and email config."""
    config_ids = {config['id'] for config in configs}
    valid = []
    
    for section in sections:
        if section.sectionid in config_ids:
            # Set email prefix from config
            for config in configs:
                if config['id'] == section.sectionid:
                    section.email_prefix = config['email']
                    break
            valid.append(section)
    
    return valid


def process_section(section: Section):
    """Load members for a section and sync to Google groups."""
    if not section.current_term:
        print(f'Warning: No current term for {section.sectionname}')
        return
    
    # Load members from OSM
    print(f'\nProcessing {section.sectionname}...')
    section.members = osm_calls.get_members(section.sectionid, section.current_term.termid)
    print(f'  Found {len(section.members)} members')
    
    # Get email sets for each group type
    leaders_emails = section.get_leaders_emails()
    young_leaders_emails = section.get_young_leaders_emails()
    parents_emails = section.get_parents_emails()
    
    print(f'  Leaders: {len(leaders_emails)} emails')
    print(f'  Young Leaders: {len(young_leaders_emails)} emails')
    print(f'  Parents: {len(parents_emails)} emails')
    
    # Sync each group
    gam_groups.gam_sync_group(section.get_group_name('leaders'), leaders_emails)
    gam_groups.gam_sync_group(section.get_group_name('youngleaders'), young_leaders_emails)
    gam_groups.gam_sync_group(section.get_group_name('parents'), parents_emails)


def print_config_summary(configs: List[Dict]):
    """Print summary of loaded configuration."""
    print(f'\n{"="*60}')
    print(f'Sections found in config file: {len(configs)}')
    print(f'{"ID":<12} {"Email Prefix":<20}')
    print(f'{"-"*12} {"-"*20}')
    for config in configs:
        print(f'{config["id"]:<12} {config["email"]:<20}')


def print_sections_summary(sections: List[Section], title: str):
    """Print summary of sections."""
    print(f'\n{"="*60}')
    print(f'{title}: {len(sections)}')
    print(f'{"Section ID":<12} {"Section Name":<30}')
    print(f'{"-"*12} {"-"*30}')
    for section in sections:
        print(f'{section.sectionid:<12} {section.sectionname:<30}')


def print_sections_with_terms(sections: List[Section], title: str):
    """Print summary of sections with term information."""
    print(f'\n{"="*60}')
    print(f'{title}: {len(sections)}')
    print(f'{"Section ID":<12} {"Section Name":<25} {"Term Start":<12}')
    print(f'{"-"*12} {"-"*25} {"-"*12}')
    for section in sections:
        term_start = section.current_term.startdate.isoformat() if section.current_term else 'N/A'
        print(f'{section.sectionid:<12} {section.sectionname:<25} {term_start:<12}')


if __name__ == '__main__':
    main()
