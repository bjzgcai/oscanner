#!/usr/bin/env python3
"""Test deck and voice API endpoints with authentication."""

import requests
import json
import os

# Disable proxy for local testing
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

BASE_URL = "http://127.0.0.1:8765"

def test_api_endpoints():
    print("🧪 Testing Deck & Voice API Endpoints...\n")

    # Step 1: Register or login to get token
    print("--- Step 1: Authentication ---")

    # Try to register (will fail if user exists, that's ok)
    register_data = {
        "email": "test@example.com",
        "password": "test123",
        "display_name": "Test User"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/register", json=register_data)
        if response.status_code == 200:
            token = response.json()['token']
            print(f"✅ Registered new user")
        else:
            print(f"⚠️  Registration failed (user may exist): {response.status_code}")
            # Try login instead
            login_data = {
                "email": "test@example.com",
                "password": "test123"
            }
            response = requests.post(f"{BASE_URL}/api/login", json=login_data)
            if response.status_code != 200:
                print(f"❌ Login failed: {response.status_code}")
                print(response.text)
                return
            token = response.json()['token']
            print(f"✅ Logged in existing user")
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    print(f"Token: {token[:20]}...\n")

    # Step 2: List decks (should see 3 system decks)
    print("--- Step 2: List decks ---")
    response = requests.get(f"{BASE_URL}/api/decks", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    decks = response.json()['decks']
    print(f"✅ Found {len(decks)} decks:")
    for deck in decks:
        print(f"   - {deck['name']} ({deck['id']}) - {deck['voice_count']} voices, system={deck['is_system']}")

    # Step 3: Get deck with voices
    print("\n--- Step 3: Get introspection deck with voices ---")
    response = requests.get(f"{BASE_URL}/api/decks/introspection_deck", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    deck_detail = response.json()
    print(f"✅ Deck: {deck_detail['name']}")
    print(f"   Voices ({len(deck_detail['voices'])}):")
    for voice in deck_detail['voices'][:3]:  # Show first 3
        print(f"   - {voice['name']} ({voice['id']})")

    # Step 4: Fork a deck
    print("\n--- Step 4: Fork introspection deck ---")
    response = requests.post(f"{BASE_URL}/api/decks/introspection_deck/fork", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    forked_deck_id = response.json()['deck_id']
    print(f"✅ Forked deck: {forked_deck_id}")

    # Verify fork
    response = requests.get(f"{BASE_URL}/api/decks/{forked_deck_id}", headers=headers)
    assert response.status_code == 200
    forked_deck = response.json()
    print(f"   Name: {forked_deck['name']}")
    print(f"   Voices: {len(forked_deck['voices'])}")
    print(f"   Parent: {forked_deck['parent_id']}")
    print(f"   Is system: {forked_deck['is_system']}")
    print(f"   Owner: {forked_deck['owner_id']}")

    # Step 5: Update forked deck
    print("\n--- Step 5: Update forked deck ---")
    update_data = {
        "name": "My Custom Introspection Deck",
        "description": "This is my personal version"
    }
    response = requests.put(f"{BASE_URL}/api/decks/{forked_deck_id}", json=update_data, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print(f"✅ Updated deck")

    # Verify update
    response = requests.get(f"{BASE_URL}/api/decks/{forked_deck_id}", headers=headers)
    updated_deck = response.json()
    print(f"   New name: {updated_deck['name']}")
    print(f"   New description: {updated_deck['description']}")

    # Step 6: Try to update system deck (should fail)
    print("\n--- Step 6: Try to update system deck (should fail) ---")
    response = requests.put(f"{BASE_URL}/api/decks/introspection_deck",
                           json={"name": "Hacked"}, headers=headers)
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    print(f"✅ Correctly rejected (404): {response.json()['detail']}")

    # Step 7: Create a voice in forked deck
    print("\n--- Step 7: Create voice in forked deck ---")
    voice_data = {
        "deck_id": forked_deck_id,
        "name": "Test Voice",
        "system_prompt": "This is a test voice prompt for testing.",
        "icon": "fire",
        "color": "blue"
    }
    response = requests.post(f"{BASE_URL}/api/voices", json=voice_data, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    new_voice_id = response.json()['voice_id']
    print(f"✅ Created voice: {new_voice_id}")

    # Verify creation
    response = requests.get(f"{BASE_URL}/api/decks/{forked_deck_id}", headers=headers)
    deck_with_new_voice = response.json()
    print(f"   Deck now has {len(deck_with_new_voice['voices'])} voices")

    # Step 8: Update voice
    print("\n--- Step 8: Update voice ---")
    voice_update = {
        "name": "Updated Test Voice",
        "system_prompt": "Updated prompt text"
    }
    response = requests.put(f"{BASE_URL}/api/voices/{new_voice_id}", json=voice_update, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print(f"✅ Updated voice")

    # Step 9: Fork a voice to forked deck
    print("\n--- Step 9: Fork a voice ---")
    fork_voice_data = {"target_deck_id": forked_deck_id}
    response = requests.post(f"{BASE_URL}/api/voices/holder/fork",
                            json=fork_voice_data, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    forked_voice_id = response.json()['voice_id']
    print(f"✅ Forked voice holder → {forked_voice_id}")

    # Verify fork
    response = requests.get(f"{BASE_URL}/api/decks/{forked_deck_id}", headers=headers)
    deck_after_voice_fork = response.json()
    print(f"   Deck now has {len(deck_after_voice_fork['voices'])} voices")

    # Step 10: Delete voice
    print("\n--- Step 10: Delete voice ---")
    response = requests.delete(f"{BASE_URL}/api/voices/{new_voice_id}", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print(f"✅ Deleted voice")

    # Verify deletion
    response = requests.get(f"{BASE_URL}/api/decks/{forked_deck_id}", headers=headers)
    deck_after_delete = response.json()
    print(f"   Deck now has {len(deck_after_delete['voices'])} voices")

    # Step 11: Create a new deck from scratch
    print("\n--- Step 11: Create new deck from scratch ---")
    new_deck_data = {
        "name": "My Personal Deck",
        "description": "A deck I created myself",
        "icon": "compass",
        "color": "green"
    }
    response = requests.post(f"{BASE_URL}/api/decks", json=new_deck_data, headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    new_deck_id = response.json()['deck_id']
    print(f"✅ Created deck: {new_deck_id}")

    # Step 12: Delete forked deck (cascade test)
    print("\n--- Step 12: Delete forked deck (cascade) ---")
    response = requests.delete(f"{BASE_URL}/api/decks/{forked_deck_id}", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print(f"✅ Deleted deck (all voices should be deleted too)")

    # Verify deletion
    response = requests.get(f"{BASE_URL}/api/decks", headers=headers)
    final_decks = response.json()['decks']
    print(f"   User now has {len(final_decks)} decks")

    # Step 13: Clean up - delete new deck
    print("\n--- Step 13: Clean up ---")
    response = requests.delete(f"{BASE_URL}/api/decks/{new_deck_id}", headers=headers)
    assert response.status_code == 200
    print(f"✅ Cleaned up test deck")

    print("\n" + "="*60)
    print("✅ All API endpoint tests passed!")
    print("="*60)

if __name__ == "__main__":
    import sys
    try:
        test_api_endpoints()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {BASE_URL}")
        print("Make sure the server is running: cd backend && python server.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
