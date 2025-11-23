"""
Data models for Online Scout Manager entities.
Using dataclasses for clean, type-safe object representation.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict
import re


EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


@dataclass
class Contact:
    """Represents a contact person (parent/guardian) for a member."""
    first_name: str
    last_name: str
    email_1: Optional[str] = None
    email_2: Optional[str] = None
    
    def get_valid_emails(self) -> List[str]:
        """Return list of valid email addresses for this contact (normalized to lowercase)."""
        valid_emails = []
        for email in [self.email_1, self.email_2]:
            if email and EMAIL_REGEX.match(email):
                valid_emails.append(email.lower())  # Normalize to lowercase
        return valid_emails
    
    @property
    def full_name(self) -> str:
        """Return full name of contact."""
        return f"{self.first_name} {self.last_name}"


@dataclass
class Member:
    """Represents a member in a scout section."""
    member_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    patrol: str
    section_id: str
    joined: Optional[date] = None
    started: Optional[date] = None
    member_email_1: Optional[str] = None  # Member's own email address 1
    member_email_2: Optional[str] = None  # Member's own email address 2
    contacts: List[Contact] = field(default_factory=list)
    
    def age_at_date(self, reference_date: date) -> int:
        """Calculate age at a given reference date."""
        return reference_date.year - self.date_of_birth.year - (
            (reference_date.month, reference_date.day) < 
            (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    @property
    def age_today(self) -> int:
        """Calculate current age."""
        return self.age_at_date(date.today())
    
    @property
    def is_leader(self) -> bool:
        """Check if member is in the Leaders or Young Leaders patrol."""
        return self.patrol in ('Leaders', 'Young Leaders (YLs)')
    
    @property
    def is_adult_leader(self) -> bool:
        """Check if member is an adult leader (18+)."""
        return self.is_leader and self.age_today >= 18
    
    @property
    def is_young_leader(self) -> bool:
        """Check if member is a young leader (<18)."""
        return self.is_leader and self.age_today < 18
    
    @property
    def full_name(self) -> str:
        """Return full name of member."""
        return f"{self.first_name} {self.last_name}"
    
    def get_contact_emails(self) -> List[str]:
        """Get all valid email addresses including member's own emails and all contacts."""
        all_emails = []
        
        # Add member's own emails if they exist and are valid
        for member_email in [self.member_email_1, self.member_email_2]:
            if member_email:
                email_lower = member_email.lower()
                if EMAIL_REGEX.match(email_lower):
                    # Normalize googlemail.com to gmail.com (Google Groups converts them)
                    email_lower = email_lower.replace('@googlemail.com', '@gmail.com')
                    all_emails.append(email_lower)
        
        # Add all contact emails
        for contact in self.contacts:
            emails = contact.get_valid_emails()
            # Normalize googlemail.com to gmail.com for all contact emails
            emails = [email.replace('@googlemail.com', '@gmail.com') for email in emails]
            all_emails.extend(emails)
        
        return all_emails
    
    @classmethod
    def from_osm_dict(cls, data: Dict) -> 'Member':
        """Create Member instance from OSM API response dictionary."""
        # Parse dates
        dob = date.fromisoformat(data['date_of_birth'])
        joined = date.fromisoformat(data['joined']) if data.get('joined') else None
        started = date.fromisoformat(data['started']) if data.get('started') else None
        
        # Parse member's own emails from custom_data group 6, fields 12 and 14
        member_email_1 = None
        member_email_2 = None
        if 'custom_data' in data and '6' in data['custom_data']:
            member_custom = data['custom_data']['6']
            if isinstance(member_custom, dict):
                member_email_1 = member_custom.get('12')
                member_email_2 = member_custom.get('14')
        
        # Parse contacts from custom_data
        contacts = []
        if 'custom_data' in data:
            for contact_num in ['1', '2']:
                if contact_num in data['custom_data']:
                    contact_data = data['custom_data'][contact_num]
                    # Skip if contact_data is not a dict (e.g., empty list)
                    if not isinstance(contact_data, dict):
                        continue
                    contact = Contact(
                        first_name=contact_data.get('2', ''),
                        last_name=contact_data.get('3', ''),
                        email_1=contact_data.get('12'),
                        email_2=contact_data.get('14')
                    )
                    if contact.first_name or contact.last_name or contact.get_valid_emails():
                        contacts.append(contact)
        
        return cls(
            member_id=data['member_id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            date_of_birth=dob,
            patrol=data['patrol'],
            section_id=data['section_id'],
            joined=joined,
            started=started,
            member_email_1=member_email_1,
            member_email_2=member_email_2,
            contacts=contacts
        )


@dataclass
class Term:
    """Represents a term/session within a section."""
    termid: str
    sectionid: str
    name: str
    startdate: date
    enddate: date
    
    @property
    def is_current(self) -> bool:
        """Check if term is currently active."""
        today = date.today()
        return self.startdate <= today <= self.enddate
    
    @property
    def has_started(self) -> bool:
        """Check if term has started."""
        return date.today() >= self.startdate
    
    @classmethod
    def from_osm_dict(cls, data: Dict) -> 'Term':
        """Create Term instance from OSM API response dictionary."""
        return cls(
            termid=data['termid'],
            sectionid=data['sectionid'],
            name=data['name'],
            startdate=date.fromisoformat(data['startdate']),
            enddate=date.fromisoformat(data['enddate'])
        )


@dataclass
class Section:
    """Represents a scout section (Beavers, Cubs, Scouts, etc.)."""
    sectionid: str
    sectionname: str
    section: str  # Section type (beavers, cubs, scouts)
    current_term: Optional[Term] = None
    email_prefix: Optional[str] = None
    members: List[Member] = field(default_factory=list)
    
    def get_leaders_emails(self) -> set:
        """Get email addresses of adult leaders (18+)."""
        emails = set()
        for member in self.members:
            if member.is_adult_leader:
                emails.update(member.get_contact_emails())
        return emails
    
    def get_young_leaders_emails(self) -> set:
        """Get email addresses of young leaders (<18) and their parents.
        
        This includes all email addresses from the young leader's contact records,
        which typically includes both parent emails and the young leader's own email.
        """
        emails = set()
        for member in self.members:
            if member.is_young_leader:
                emails.update(member.get_contact_emails())
        return emails
    
    def get_parents_emails(self) -> set:
        """Get email addresses of parents (non-leader members)."""
        emails = set()
        for member in self.members:
            if not member.is_leader:
                emails.update(member.get_contact_emails())
        return emails
    
    def get_group_name(self, group_type: str) -> str:
        """
        Get Google group name for this section.
        
        Args:
            group_type: One of 'leaders', 'youngleaders', 'parents'
        
        Returns:
            Full group email name (e.g., 'tomleaders')
        """
        if not self.email_prefix:
            raise ValueError(f"No email_prefix set for section {self.sectionid}")
        return f"{self.email_prefix}{group_type}"
    
    @classmethod
    def from_osm_dict(cls, data: Dict) -> 'Section':
        """Create Section instance from OSM API response dictionary."""
        return cls(
            sectionid=data['sectionid'],
            sectionname=data['sectionname'],
            section=data['section']
        )
    
    def to_dict(self) -> Dict:
        """Convert section to dictionary for display/logging."""
        return {
            'sectionid': self.sectionid,
            'sectionname': self.sectionname,
            'section': self.section,
            'term_name': self.current_term.name if self.current_term else None,
            'start_date': self.current_term.startdate.isoformat() if self.current_term else None,
            'member_count': len(self.members)
        }
