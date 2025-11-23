"""
Restore Google Groups to a previous snapshot state.
Usage: python restore_groups.py <snapshot_file>
"""
import json
import sys
from pathlib import Path
from src.gsuite_sync.groups_api import GoogleGroupsManager
from src.config_manager import get_config_manager

def restore_groups(snapshot_file: str, dry_run: bool = True):
    """Restore groups to snapshot state."""
    # Load snapshot
    snapshot_path = Path('output') / snapshot_file if not Path(snapshot_file).exists() else Path(snapshot_file)
    
    if not snapshot_path.exists():
        print(f"❌ Snapshot file not found: {snapshot_path}")
        return
    
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        snapshot = json.load(f)
    
    print(f"📂 Loading snapshot from: {snapshot_path}")
    print(f"   Timestamp: {snapshot['timestamp']}")
    print(f"   Domain: {snapshot['domain']}")
    print(f"   Groups: {len(snapshot['groups'])}")
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")
    else:
        print("\n⚠️  LIVE MODE - Groups will be modified!\n")
    
    # Load current config
    config_mgr = get_config_manager()
    google_config = config_mgr.load_google_config()
    domain = google_config['domain']
    
    # Initialize Google Groups Manager
    manager = GoogleGroupsManager(domain=domain, dry_run=dry_run)
    
    # Restore each group
    for group_name, group_data in snapshot['groups'].items():
        if 'error' in group_data:
            print(f"⏭️  Skipping {group_name} (had error in snapshot)")
            continue
        
        snapshot_members = set(group_data['members'])
        full_email = group_data['full_email']
        print(f"\n🔄 Restoring {group_name}...")
        print(f"   Snapshot had {len(snapshot_members)} members")
        
        try:
            # Get current members
            current_members = manager.get_group_members(full_email)
            print(f"   Current has {len(current_members)} members")
            
            # Calculate differences
            to_add = snapshot_members - current_members
            to_remove = current_members - snapshot_members
            
            if not to_add and not to_remove:
                print(f"   ✓ Already matches snapshot (no changes needed)")
                continue
            
            if to_add:
                print(f"   📥 Will add {len(to_add)} members:")
                for email in sorted(list(to_add))[:5]:  # Show first 5
                    print(f"      + {email}")
                if len(to_add) > 5:
                    print(f"      ... and {len(to_add) - 5} more")
            
            if to_remove:
                print(f"   📤 Will remove {len(to_remove)} members:")
                for email in sorted(list(to_remove))[:5]:  # Show first 5
                    print(f"      - {email}")
                if len(to_remove) > 5:
                    print(f"      ... and {len(to_remove) - 5} more")
            
            # Perform sync to restore snapshot state
            if not dry_run:
                manager.sync_group(full_email, snapshot_members)
                print(f"   ✅ Restored successfully")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    if dry_run:
        print("\n" + "=" * 60)
        print("🔍 Dry run complete. No changes were made.")
        print("   To restore for real, run:")
        print(f"   python restore_groups.py {snapshot_file} --live")
    else:
        print("\n" + "=" * 60)
        print("✅ Restore complete!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python restore_groups.py <snapshot_file> [--live]")
        print("\nAvailable snapshots:")
        output_dir = Path('output')
        if output_dir.exists():
            snapshots = sorted(output_dir.glob('group_snapshot_*.json'), reverse=True)
            if snapshots:
                for snap in snapshots:
                    print(f"  - {snap.name}")
            else:
                print("  No snapshots found")
        sys.exit(1)
    
    snapshot_file = sys.argv[1]
    dry_run = '--live' not in sys.argv
    
    print("🔄 Restoring Google Groups from snapshot...")
    print("=" * 60)
    restore_groups(snapshot_file, dry_run=dry_run)
    print("=" * 60)
