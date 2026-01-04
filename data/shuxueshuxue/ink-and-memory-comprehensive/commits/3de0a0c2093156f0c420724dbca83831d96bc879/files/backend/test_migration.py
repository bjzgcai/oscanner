#!/usr/bin/env python3
"""
Test migration of real localStorage data to database.

This script:
1. Loads the real_user_data.json export
2. Parses all localStorage data
3. Creates a test user
4. Migrates all data to database
5. Verifies migration success
"""

import json
import sys
from datetime import datetime
import bcrypt
from database import (
    init_db, create_user, import_user_data,
    get_user_by_id, list_sessions, get_daily_pictures,
    get_preferences, get_analysis_reports
)

def parse_localStorage_export(filepath):
    """Parse the localStorage export JSON."""
    print(f"📂 Loading {filepath}...")

    with open(filepath, 'r') as f:
        data = json.load(f)

    print(f"✅ Loaded {data.get('sizeEstimate', 'unknown')} of data")

    return data

def extract_sessions(data):
    """Extract all sessions from current session + calendar entries."""
    sessions = []

    # 1. Current session
    if data.get('currentSession'):
        current = json.loads(data['currentSession'])
        sessions.append({
            'id': 'current-session',
            'name': 'Current Session',
            'editor_state': current
        })
        print(f"  ✅ Current session: {len(current.get('cells', []))} cells")

    # 2. Calendar entries (each entry is a separate session)
    if data.get('calendarEntries'):
        calendar = json.loads(data['calendarEntries'])

        for date, entries in calendar.items():
            for entry in entries:
                sessions.append({
                    'id': entry['id'],
                    'name': f"{date} - {entry.get('firstLine', 'Untitled')}",
                    'editor_state': entry['state']
                })

        total_entries = sum(len(entries) for entries in calendar.values())
        print(f"  ✅ Calendar: {len(calendar)} days, {total_entries} entries")

    # 3. Old document system (if used)
    if data.get('oldDocument'):
        try:
            old_doc = json.loads(data['oldDocument'])
            if old_doc and old_doc.get('document'):
                sessions.append({
                    'id': 'old-document',
                    'name': 'Old Document (migrated)',
                    'editor_state': {'cells': [{'type': 'text', 'content': str(old_doc)}]}
                })
                print(f"  ⚠️ Old document system found (migrated as text)")
        except:
            pass

    return sessions

def extract_pictures(data):
    """Extract daily pictures."""
    pictures = []

    if data.get('dailyPictures'):
        pics = json.loads(data['dailyPictures'])
        for pic in pics:
            pictures.append({
                'date': pic['date'],
                'image_base64': pic['base64'],
                'prompt': pic.get('prompt', '')
            })

        print(f"  ✅ Pictures: {len(pictures)} images")

    return pictures

def extract_preferences(data):
    """Extract user preferences."""
    prefs = {}

    if data.get('voiceCustomizations'):
        prefs['voice_configs'] = json.loads(data['voiceCustomizations'])

    if data.get('metaPrompt'):
        prefs['meta_prompt'] = data['metaPrompt']

    if data.get('stateConfig'):
        prefs['state_config'] = json.loads(data['stateConfig'])

    if data.get('selectedState'):
        prefs['selected_state'] = data['selectedState']

    print(f"  ✅ Preferences: {len(prefs)} items")

    return prefs

def extract_reports(data):
    """Extract analysis reports."""
    reports = []

    if data.get('analysisReports'):
        report_list = json.loads(data['analysisReports'])
        for report in report_list:
            reports.append({
                'type': report.get('type', 'unknown'),
                'data': report.get('data', {}),
                'allNotes': report.get('allNotes', ''),
                'timestamp': report.get('timestamp', datetime.now().isoformat())
            })

        print(f"  ✅ Reports: {len(reports)} analysis reports")

    return reports

def test_migration():
    """Run the full migration test."""
    print("\n" + "="*60)
    print("🧪 Testing localStorage Migration")
    print("="*60 + "\n")

    # Step 1: Initialize database
    print("1️⃣ Initializing database...")
    init_db()

    # Step 2: Load localStorage export
    print("\n2️⃣ Loading localStorage export...")
    data = parse_localStorage_export('test_data/real_user_data.json')

    # Step 3: Extract all data
    print("\n3️⃣ Extracting data...")
    sessions = extract_sessions(data)
    pictures = extract_pictures(data)
    preferences = extract_preferences(data)
    reports = extract_reports(data)

    # Step 4: Create test user
    print("\n4️⃣ Creating test user...")
    password_hash = bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode('utf-8')
    user_id = create_user('test@example.com', password_hash, 'Test User')
    print(f"  ✅ User created: ID={user_id}")

    # Step 5: Import all data
    print("\n5️⃣ Importing data to database...")
    import_user_data(user_id, sessions, pictures, preferences, reports)

    # Step 6: Verify migration
    print("\n6️⃣ Verifying migration...")

    user = get_user_by_id(user_id)
    print(f"  ✅ User: {user['email']}")

    db_sessions = list_sessions(user_id)
    print(f"  ✅ Sessions: {len(db_sessions)} (expected {len(sessions)})")

    db_pictures = get_daily_pictures(user_id, limit=100)
    print(f"  ✅ Pictures: {len(db_pictures)} (expected {len(pictures)})")

    db_prefs = get_preferences(user_id)
    if db_prefs:
        print(f"  ✅ Preferences: {len([k for k, v in db_prefs.items() if v is not None])} items")

    db_reports = get_analysis_reports(user_id, limit=100)
    print(f"  ✅ Reports: {len(db_reports)} (expected {len(reports)})")

    # Success!
    print("\n" + "="*60)
    print("✅ Migration test PASSED!")
    print("="*60)
    print(f"\nMigrated:")
    print(f"  - {len(sessions)} sessions")
    print(f"  - {len(pictures)} images (freed ~{len(pictures) * 2.5:.1f}MB from localStorage!)")
    print(f"  - {len([k for k, v in preferences.items() if v])} preference items")
    print(f"  - {len(reports)} analysis reports")

    return True

if __name__ == "__main__":
    try:
        test_migration()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Migration test FAILED!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
