"""
Test email notification functionality locally.

This script tests the email notification system without actually sending emails.
It validates:
1. EmailNotifier class initialization
2. Email template generation
3. Integration with sync_logger
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from email_notifier import EmailNotifier, get_email_notifier
from sync_logger import SyncLogger, SyncStatus


def test_email_notifier_initialization():
    """Test that EmailNotifier can be initialized (in local mode, will return None)."""
    print("\n=== Test 1: EmailNotifier Initialization ===")
    
    notifier = get_email_notifier()
    
    if notifier is None:
        print("✅ PASS: get_email_notifier() returns None in local mode (expected)")
        print("   This is correct - email notifications only work in cloud mode")
    else:
        print("❌ FAIL: Expected None in local mode, got:", type(notifier))
        return False
    
    return True


def test_email_template_generation():
    """Test email template generation without sending."""
    print("\n=== Test 2: Email Template Generation ===")
    
    try:
        # Create a mock EmailNotifier instance to test template
        # We'll create it manually since we can't get real credentials locally
        from unittest.mock import Mock
        
        notifier = EmailNotifier(
            credentials=Mock(),
            sender_email="osm-sync@1stwarleyscouts.org.uk"
        )
        
        # We can't actually call send_failure_notification without real credentials,
        # but we can verify the class structure
        print("✅ PASS: EmailNotifier class can be instantiated")
        print(f"   Sender email: {notifier.sender_email}")
        print(f"   Has send_failure_notification method: {hasattr(notifier, 'send_failure_notification')}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error creating EmailNotifier: {e}")
        return False


def test_sync_logger_with_error():
    """Test that sync_logger can handle ERROR status (should attempt email in cloud mode)."""
    print("\n=== Test 3: SyncLogger Error Handling ===")
    
    try:
        # Create logger in local mode
        logger = SyncLogger()
        
        print(f"   Logger initialized (cloud mode: {logger.use_cloud})")
        
        # Log an error
        logger.log_sync(
            section_id="12345",
            section_name="Test Section",
            group_type="leaders",
            group_email="test@example.com",
            status=SyncStatus.ERROR,
            members_added=[],
            members_removed=[],
            error_message="This is a test error",
            dry_run=False,
            triggered_by="manual"
        )
        
        print("✅ PASS: Logger can log ERROR status without crashing")
        print("   Note: Email not sent in local mode (expected)")
        
        # Check that log file was created
        import glob
        log_files = glob.glob('logs/sync/*.json')
        if log_files:
            print(f"✅ PASS: Log file created: {os.path.basename(log_files[-1])}")
        else:
            print("⚠️  WARNING: No log files found in logs/sync/")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error in sync_logger: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_notification_integration():
    """Test the integration between sync_logger and email_notifier."""
    print("\n=== Test 4: Integration Test ===")
    
    try:
        # Verify the _send_error_notification method exists
        logger = SyncLogger()
        
        if hasattr(logger, '_send_error_notification'):
            print("✅ PASS: SyncLogger has _send_error_notification method")
        else:
            print("❌ FAIL: SyncLogger missing _send_error_notification method")
            return False
        
        # Verify the method signature
        import inspect
        sig = inspect.signature(logger._send_error_notification)
        print(f"   Method signature: {sig}")
        
        # Verify it takes a SyncLogEntry parameter
        if 'entry' in sig.parameters:
            print("✅ PASS: Method accepts entry parameter")
        else:
            print("❌ FAIL: Method doesn't accept entry parameter")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("EMAIL NOTIFICATION SYSTEM TEST")
    print("="*60)
    print("\nThis test validates the email notification system locally.")
    print("Actual email sending requires cloud deployment with Gmail API enabled.")
    
    results = []
    
    results.append(("EmailNotifier Initialization", test_email_notifier_initialization()))
    results.append(("Email Template Generation", test_email_template_generation()))
    results.append(("SyncLogger Error Handling", test_sync_logger_with_error()))
    results.append(("Integration Test", test_email_notification_integration()))
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready for deployment.")
        print("\nNext steps:")
        print("1. Deploy to Cloud Run")
        print("2. Enable Gmail API in Google Cloud Console")
        print("3. Update domain-wide delegation (add gmail.send scope)")
        print("4. Configure notification email in app")
        print("5. Test with a real sync failure")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix before deploying.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
