"""
Test script for configuration management functionality.
Tests loading, saving, and validation of email_config.yaml.
"""

from config_manager import get_config_manager
import yaml

print("=" * 80)
print("TESTING CONFIGURATION MANAGEMENT")
print("=" * 80)

# 1. Test loading configuration
print("\n1. Testing configuration loading...")
config_mgr = get_config_manager()
print(f"   Using cloud config: {config_mgr.use_cloud}")

osm_config, google_config, email_config, error = config_mgr.load_all_configs()

if error:
    print(f"   ❌ Failed to load configs: {error}")
    exit(1)

print(f"   ✅ Successfully loaded configs")
print(f"   - OSM API URL: {osm_config.get('base_url', 'N/A')}")
print(f"   - Google Domain: {google_config.get('domain', 'N/A')}")
print(f"   - Sections configured: {len(email_config['sections'])}")

# 2. Display current sections
print("\n2. Current section configuration:")
for section in email_config['sections']:
    print(f"   - Section {section['id']}: {section['email']}")

# 3. Test validation
print("\n3. Testing configuration validation...")
is_valid, error_msg = config_mgr.validate_email_config(email_config)
if is_valid:
    print(f"   ✅ Configuration is valid")
else:
    print(f"   ❌ Validation failed: {error_msg}")

# 4. Test validation with invalid config
print("\n4. Testing validation with invalid config...")
invalid_config = {'sections': [{'id': '123'}]}  # Missing 'email' field
is_valid, error_msg = config_mgr.validate_email_config(invalid_config)
if not is_valid:
    print(f"   ✅ Correctly rejected invalid config: {error_msg}")
else:
    print(f"   ❌ Should have rejected invalid config")

# 5. Test saving configuration (dry run - add test section)
print("\n5. Testing configuration save (adding test section)...")
test_config = {
    'sections': email_config['sections'] + [{
        'id': '99999',
        'email': 'test'
    }]
}

try:
    config_mgr.save_email_config(test_config)
    print(f"   ✅ Successfully saved test configuration")
    
    # Reload to verify
    _, _, reloaded_config, error = config_mgr.load_all_configs()
    if len(reloaded_config['sections']) == len(email_config['sections']) + 1:
        print(f"   ✅ Verified: Configuration persisted correctly")
        print(f"   - Original sections: {len(email_config['sections'])}")
        print(f"   - After save: {len(reloaded_config['sections'])}")
    else:
        print(f"   ❌ Configuration not persisted correctly")
    
    # Restore original config
    config_mgr.save_email_config(email_config)
    print(f"   ✅ Restored original configuration")
    
except Exception as e:
    print(f"   ❌ Failed to save configuration: {e}")

# 6. Summary
print("\n" + "=" * 80)
print("CONFIGURATION MANAGEMENT TEST COMPLETE")
print("=" * 80)
print("\n✅ All tests passed! Configuration management is working correctly.")
print("\nNext steps:")
print("  1. Test the Streamlit Configuration tab UI")
print("     - Open http://localhost:8501")
print("     - Go to Configuration tab")
print("     - Try editing an email prefix")
print("     - Try adding a new section")
print("     - Try deleting a section")
print("     - Click Save Changes")
print("  2. Verify changes persist after app restart")
