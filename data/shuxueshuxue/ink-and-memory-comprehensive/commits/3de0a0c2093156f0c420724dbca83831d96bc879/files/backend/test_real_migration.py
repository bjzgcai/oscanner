#!/usr/bin/env python3
"""
Test full migration flow with real user data.

Simulates:
1. User registers
2. User logs in
3. Frontend sends localStorage data
4. Backend imports to database
5. Frontend fetches data back
"""

import requests
import json

API_BASE = "http://localhost:8765"

def test_full_migration():
    print("\n" + "="*60)
    print("🧪 Testing Full Migration with Real Data")
    print("="*60 + "\n")

    # Load real localStorage export
    print("📂 Loading real localStorage export...")
    with open('test_data/real_user_data.json', 'r') as f:
        real_data = json.load(f)

    print(f"✅ Loaded {real_data.get('sizeEstimate', 'unknown')}")
    print()

    # Step 1: Register
    print("1️⃣ Registering new user...")
    register_response = requests.post(
        f"{API_BASE}/api/register",
        json={
            "email": "realuser@example.com",
            "password": "password123",
            "display_name": "Real User"
        }
    )

    if register_response.status_code != 200:
        print(f"❌ Registration failed: {register_response.text}")
        return False

    register_data = register_response.json()
    token = register_data['token']
    user_id = register_data['user']['id']
    print(f"✅ User registered: ID={user_id}")
    print()

    # Step 2: Import localStorage data
    print("2️⃣ Importing localStorage data...")

    # Prepare import request (match frontend localStorage keys)
    import_request = {
        "currentSession": real_data.get('currentSession'),
        "calendarEntries": real_data.get('calendarEntries'),
        "dailyPictures": real_data.get('dailyPictures'),
        "voiceCustomizations": real_data.get('voiceCustomizations'),
        "metaPrompt": real_data.get('metaPrompt'),
        "stateConfig": real_data.get('stateConfig'),
        "selectedState": real_data.get('selectedState'),
        "analysisReports": real_data.get('analysisReports'),
        "oldDocument": real_data.get('oldDocument')
    }

    import_response = requests.post(
        f"{API_BASE}/api/import-local-data",
        headers={"Authorization": f"Bearer {token}"},
        json=import_request
    )

    if import_response.status_code != 200:
        print(f"❌ Import failed: {import_response.text}")
        return False

    import_result = import_response.json()
    print(f"✅ Import successful!")
    print(f"   Sessions: {import_result['imported']['sessions']}")
    print(f"   Pictures: {import_result['imported']['pictures']}")
    print(f"   Preferences: {import_result['imported']['preferences']}")
    print(f"   Reports: {import_result['imported']['reports']}")
    print()

    # Step 3: Verify - List sessions
    print("3️⃣ Verifying data - List sessions...")
    sessions_response = requests.get(
        f"{API_BASE}/api/sessions",
        headers={"Authorization": f"Bearer {token}"}
    )

    if sessions_response.status_code != 200:
        print(f"❌ Failed to list sessions: {sessions_response.text}")
        return False

    sessions = sessions_response.json()['sessions']
    print(f"✅ Found {len(sessions)} sessions:")
    for session in sessions[:3]:  # Show first 3
        print(f"   - {session['name']} (updated: {session['updated_at']})")
    if len(sessions) > 3:
        print(f"   ... and {len(sessions) - 3} more")
    print()

    # Step 4: Verify - Get a session's full state
    if sessions:
        print("4️⃣ Fetching full session state...")
        session_id = sessions[0]['id']
        session_response = requests.get(
            f"{API_BASE}/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        if session_response.status_code != 200:
            print(f"❌ Failed to get session: {session_response.text}")
            return False

        session_data = session_response.json()
        editor_state = session_data['editor_state']
        num_cells = len(editor_state.get('cells', []))
        print(f"✅ Session '{session_data['name']}' has {num_cells} cells")
        print()

    # Step 5: Verify - Get pictures
    print("5️⃣ Verifying pictures...")
    pictures_response = requests.get(
        f"{API_BASE}/api/pictures?limit=10",
        headers={"Authorization": f"Bearer {token}"}
    )

    if pictures_response.status_code != 200:
        print(f"❌ Failed to get pictures: {pictures_response.text}")
        return False

    pictures = pictures_response.json()['pictures']
    print(f"✅ Found {len(pictures)} pictures:")
    for pic in pictures:
        size_kb = len(pic['image_base64']) / 1024
        print(f"   - {pic['date']}: {size_kb:.1f} KB ({pic.get('prompt', 'no prompt')[:50]}...)")

    total_size_mb = sum(len(p['image_base64']) for p in pictures) / 1024 / 1024
    print(f"   Total: {total_size_mb:.2f} MB (was in localStorage!)")
    print()

    # Step 6: Verify - Get preferences
    print("6️⃣ Verifying preferences...")
    prefs_response = requests.get(
        f"{API_BASE}/api/preferences",
        headers={"Authorization": f"Bearer {token}"}
    )

    if prefs_response.status_code != 200:
        print(f"❌ Failed to get preferences: {prefs_response.text}")
        return False

    prefs = prefs_response.json()
    print(f"✅ Preferences loaded:")
    if prefs.get('meta_prompt'):
        print(f"   - Meta prompt: {prefs['meta_prompt'][:50]}...")
    if prefs.get('selected_state'):
        print(f"   - Selected state: {prefs['selected_state']}")
    if prefs.get('voice_configs'):
        num_voices = len(prefs['voice_configs'])
        print(f"   - Voice configs: {num_voices} voices")
    print()

    # Step 7: Verify - Get reports
    print("7️⃣ Verifying analysis reports...")
    reports_response = requests.get(
        f"{API_BASE}/api/reports?limit=10",
        headers={"Authorization": f"Bearer {token}"}
    )

    if reports_response.status_code != 200:
        print(f"❌ Failed to get reports: {reports_response.text}")
        return False

    reports = reports_response.json()['reports']
    print(f"✅ Found {reports} reports:")
    for report in reports:
        print(f"   - {report['report_type']} (created: {report['created_at']})")
    print()

    # Success summary
    print("="*60)
    print("✅ MIGRATION TEST PASSED!")
    print("="*60)
    print(f"\nMigrated from localStorage → SQLite:")
    print(f"  - {import_result['imported']['sessions']} sessions")
    print(f"  - {import_result['imported']['pictures']} pictures ({total_size_mb:.2f} MB freed!)")
    print(f"  - {import_result['imported']['preferences']} preference items")
    print(f"  - {import_result['imported']['reports']} analysis reports")
    print(f"\nAll data successfully retrieved via API!")
    print("="*60 + "\n")

    return True

if __name__ == "__main__":
    try:
        success = test_full_migration()
        if success:
            print("🎉 Ready to build frontend!")
        else:
            print("❌ Migration test failed")
            exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
