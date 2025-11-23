# Configuration Management Testing Checklist

## ✅ Automated Tests Complete

- ✅ Configuration loading works (local YAML files)
- ✅ Validation works (rejects invalid configs)
- ✅ Save functionality works (file writes correctly)
- ✅ Configuration persists after save (reload shows changes)

## 🧪 Manual UI Testing

### Test 1: Edit Existing Section Email Prefix

**Steps:**
1. Open http://localhost:8501 in browser
2. Go to **Configuration** tab
3. Find "Section 12137 (smithies)" 
4. Change email prefix from "smithies" to "smithiestest"
5. Notice "You have unsaved changes" message appears
6. Click **💾 Save Changes** button
7. Look for "✅ Configuration saved successfully!" message
8. Click **🔄 Clear Cache & Reload** in sidebar
9. Go back to Configuration tab
10. Verify the change persisted (email prefix should be "smithiestest")
11. **RESTORE**: Change back to "smithies" and save

**Expected Result:**
- ✅ Changes are saved
- ✅ Changes persist after reload
- ✅ email_config.yaml file is updated

---

### Test 2: Add New Section

**Steps:**
1. In Configuration tab, scroll to "Add New Section"
2. Enter Section ID: `99999`
3. Enter Email Prefix: `testsection`
4. Click **➕ Add** button
5. Verify success message appears
6. Scroll up to see the new section in the list
7. Click **💾 Save Changes**
8. Reload the app
9. Verify the new section still appears

**Expected Result:**
- ✅ New section added to UI
- ✅ Save button becomes enabled
- ✅ Changes persist after save and reload

**CLEANUP:**
1. Delete the test section (next test)

---

### Test 3: Delete Section

**Steps:**
1. Find the test section (ID: 99999) you just added
2. Click the **🗑️** delete button next to it
3. Verify the section disappears from the list
4. Notice "You have unsaved changes" message
5. Click **💾 Save Changes**
6. Verify "✅ Configuration saved successfully!" message
7. Reload the app
8. Verify the section is still gone

**Expected Result:**
- ✅ Section removed from UI immediately
- ✅ Changes saved to file
- ✅ Deletion persists after reload

---

### Test 4: Reset Changes

**Steps:**
1. Make a change to any email prefix
2. Notice "You have unsaved changes" message
3. Click **🔄 Reset** button
4. Verify the change is reverted
5. Verify "unsaved changes" message disappears

**Expected Result:**
- ✅ Changes are discarded
- ✅ Original values restored
- ✅ No file changes made

---

### Test 5: Validation - Invalid Email Prefix

**Steps:**
1. Try to change email prefix to contain special characters: `test@section`
2. Click **💾 Save Changes**
3. Verify validation error appears

**Expected Result:**
- ✅ Validation prevents save
- ✅ Error message shows invalid characters

---

### Test 6: Multiple Changes at Once

**Steps:**
1. Edit email prefix for one section
2. Add a new section
3. Delete another section
4. Verify message shows multiple changes (e.g., "2 edits, 1 deletions")
5. Click **💾 Save Changes**
6. Verify all changes are saved
7. Reload and verify all changes persisted

**Expected Result:**
- ✅ All changes tracked correctly
- ✅ All changes saved in single operation
- ✅ All changes persist after reload

---

## 📝 Test Results

### Test 1: Edit Email Prefix
- [ ] PASS
- [ ] FAIL: ___________

### Test 2: Add Section
- [ ] PASS
- [ ] FAIL: ___________

### Test 3: Delete Section
- [ ] PASS
- [ ] FAIL: ___________

### Test 4: Reset Changes
- [ ] PASS
- [ ] FAIL: ___________

### Test 5: Validation
- [ ] PASS
- [ ] FAIL: ___________

### Test 6: Multiple Changes
- [ ] PASS
- [ ] FAIL: ___________

---

## ✅ Post-Testing

After testing:
1. Verify `email_config.yaml` is in correct state
2. If needed, restore from backup: `cp email_config.yaml.backup email_config.yaml`
3. All 6 original sections should be present with correct prefixes

## 🐛 Issues Found

Document any issues here:

---

## ✅ Sign-Off

**Tester:** __________________
**Date:** __________________
**Result:** PASS / FAIL
**Notes:** 
