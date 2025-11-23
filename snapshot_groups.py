"""
Snapshot current state of Google Groups before live testing.
Records all members in each group so we can revert if needed.
"""
import json
from datetime import datetime
from pathlib import Path
from gsuite_sync.groups_api import GoogleGroupsManager
from config_manager import get_config_manager

def snapshot_groups():
    """Take a snapshot of all current group memberships."""
    # Load configurations
    config_mgr = get_config_manager()
    google_config = config_mgr.load_google_config()
    email_config = config_mgr.load_email_config()
    
    domain = google_config['domain']
    
    # Initialize Google Groups Manager
    manager = GoogleGroupsManager(domain=domain, dry_run=False)
    
    # Collect snapshot data
    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'domain': domain,
        'groups': {}
    }
    
    # For each section, get current members of all 3 groups
    group_types = ['leaders', 'youngleaders', 'parents']
    
    for section in email_config['sections']:
        section_email = section['email']
        section_id = section['id']
        
        print(f"\n📸 Snapshotting section: {section_email} (ID: {section_id})")
        
        for group_type in group_types:
            group_name = f"{section_email}{group_type}"
            full_email = f"{group_name}@{domain}"
            
            try:
                members = manager.get_group_members(full_email)
                snapshot['groups'][group_name] = {
                    'full_email': full_email,
                    'section_id': section_id,
                    'section_email': section_email,
                    'group_type': group_type,
                    'member_count': len(members),
                    'members': sorted(list(members))  # Convert set to sorted list for JSON
                }
                print(f"  ✓ {group_name}: {len(members)} members")
            except Exception as e:
                print(f"  ✗ {group_name}: Error - {e}")
                snapshot['groups'][group_name] = {
                    'full_email': full_email,
                    'section_id': section_id,
                    'section_email': section_email,
                    'group_type': group_type,
                    'error': str(e),
                    'members': []
                }
    
    # Save snapshot to file
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    snapshot_file = output_dir / f'group_snapshot_{timestamp_str}.json'
    
    with open(snapshot_file, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Snapshot saved to: {snapshot_file}")
    print(f"   Total groups: {len(snapshot['groups'])}")
    print(f"   Total members across all groups: {sum(g.get('member_count', 0) for g in snapshot['groups'].values())}")
    
    return snapshot_file

if __name__ == '__main__':
    print("🔍 Taking snapshot of current Google Groups state...")
    print("=" * 60)
    snapshot_file = snapshot_groups()
    print("\n" + "=" * 60)
    print("✨ Snapshot complete!")
    print(f"\n📝 To revert later, use: restore_groups.py {snapshot_file.name}")
