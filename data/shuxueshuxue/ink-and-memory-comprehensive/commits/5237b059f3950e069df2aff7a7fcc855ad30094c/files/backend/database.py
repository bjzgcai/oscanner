#!/usr/bin/env python3
"""
SQLite database setup and migrations for Ink & Memory.

Schema:
- users: User accounts (email, password_hash)
- user_sessions: Editor sessions (editor state JSON)
- daily_pictures: Generated images (base64)
- user_preferences: Voice configs, meta prompts, etc.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

# Database location
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "ink-and-memory.db"

# Ensure data directory exists
DB_DIR.mkdir(exist_ok=True)

def get_db():
    """Get database connection with WAL mode enabled."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row  # Access columns by name

    # @@@ Enable WAL mode for concurrent reads + 1 write
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    return db

def init_db():
    """Initialize database by creating all tables."""
    db = get_db()
    create_tables(db)
    db.commit()
    db.close()
    print(f"✅ Database initialized at {DB_PATH}")

    # Seed system decks
    seed_system_decks()

def create_tables(db):
    """Create all database tables."""
    print("📦 Creating database tables...")

    # Users table
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      display_name TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # User sessions (editor states)
    db.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
      id TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      name TEXT,
      editor_state_json TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")

    # Daily pictures (generated images) - no UNIQUE constraint, allows multiple per day
    db.execute("""
    CREATE TABLE IF NOT EXISTS daily_pictures (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      date TEXT NOT NULL,
      image_base64 TEXT NOT NULL,
      prompt TEXT,
      thumbnail_base64 TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_pictures_user_date ON daily_pictures(user_id, date)")

    # User preferences (voice configs, meta prompts, etc.)
    db.execute("""
    CREATE TABLE IF NOT EXISTS user_preferences (
      user_id INTEGER PRIMARY KEY,
      voice_configs_json TEXT,
      meta_prompt TEXT,
      state_config_json TEXT,
      selected_state TEXT,
      first_login_completed INTEGER DEFAULT 0,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Auth sessions
    db.execute("""
    CREATE TABLE IF NOT EXISTS auth_sessions (
      token TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      expires_at DATETIME NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_auth_user ON auth_sessions(user_id)")

    # Analysis reports
    db.execute("""
    CREATE TABLE IF NOT EXISTS analysis_reports (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      report_type TEXT NOT NULL,
      report_data_json TEXT NOT NULL,
      all_notes_text TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON analysis_reports(user_id, created_at)")

    # @@@ Decks table - organize voices into themed collections
    db.execute("""
    CREATE TABLE IF NOT EXISTS decks (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      name_zh TEXT,
      name_en TEXT,
      description TEXT,
      description_zh TEXT,
      description_en TEXT,
      icon TEXT,
      color TEXT,
      is_system BOOLEAN DEFAULT 0,
      parent_id TEXT,
      owner_id INTEGER,
      enabled BOOLEAN DEFAULT 1,
      has_local_changes BOOLEAN DEFAULT 0,
      order_index INTEGER,
      published BOOLEAN DEFAULT 0,
      author_name TEXT,
      install_count INTEGER DEFAULT 0,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (parent_id) REFERENCES decks(id),
      FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_decks_owner ON decks(owner_id)")

    # @@@ Migration: Add publishing columns to existing decks table
    try:
        db.execute("ALTER TABLE decks ADD COLUMN published BOOLEAN DEFAULT 0")
    except:
        pass  # Column already exists
    try:
        db.execute("ALTER TABLE decks ADD COLUMN author_name TEXT")
    except:
        pass
    try:
        db.execute("ALTER TABLE decks ADD COLUMN install_count INTEGER DEFAULT 0")
    except:
        pass

    # @@@ Voices table - individual voice personas within decks
    db.execute("""
    CREATE TABLE IF NOT EXISTS voices (
      id TEXT PRIMARY KEY,
      deck_id TEXT NOT NULL,
      name TEXT NOT NULL,
      name_zh TEXT,
      name_en TEXT,
      system_prompt TEXT NOT NULL,
      icon TEXT,
      color TEXT,
      is_system BOOLEAN DEFAULT 0,
      parent_id TEXT,
      owner_id INTEGER,
      enabled BOOLEAN DEFAULT 1,
      has_local_changes BOOLEAN DEFAULT 0,
      order_index INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
      FOREIGN KEY (parent_id) REFERENCES voices(id),
      FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_voices_deck ON voices(deck_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_voices_owner ON voices(owner_id)")

    print("✅ Tables created")

def seed_system_decks():
    """Seed system decks and voices. Idempotent - safe to call multiple times."""
    db = get_db()

    # Check if already seeded
    existing = db.execute("SELECT COUNT(*) FROM decks WHERE is_system = 1").fetchone()[0]
    if existing > 0:
        print("⏭️  System decks already seeded, skipping")
        db.close()
        return

    print("🌱 Seeding system decks...")

    # ========== Deck 1: Introspection Deck ==========
    db.execute("""
    INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en, icon, color, is_system, enabled, has_local_changes, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('introspection_deck', '内省卡组', '内省卡组', 'Introspection Deck',
          '内心对话原型', '内心对话原型', 'Inner dialogue archetypes',
          'brain', 'purple', 1, 1, 0, 0))

    # Import config to get existing voice prompts
    import config

    # Introspection voices (from existing VOICE_ARCHETYPES)
    introspection_voices = [
        ('holder', config.VOICE_ARCHETYPES['holder']['name'], '接纳者', 'The Holder',
         config.VOICE_ARCHETYPES['holder']['systemPrompt'], 'heart', 'pink', 0),
        ('unpacker', config.VOICE_ARCHETYPES['unpacker']['name'], '拆解者', 'The Unpacker',
         config.VOICE_ARCHETYPES['unpacker']['systemPrompt'], 'brain', 'blue', 1),
        ('starter', config.VOICE_ARCHETYPES['starter']['name'], '启动者', 'The Starter',
         config.VOICE_ARCHETYPES['starter']['systemPrompt'], 'fist', 'yellow', 2),
        ('mirror', config.VOICE_ARCHETYPES['mirror']['name'], '照镜者', 'The Mirror',
         config.VOICE_ARCHETYPES['mirror']['systemPrompt'], 'eye', 'green', 3),
        ('weaver', config.VOICE_ARCHETYPES['weaver']['name'], '连接者', 'The Weaver',
         config.VOICE_ARCHETYPES['weaver']['systemPrompt'], 'compass', 'purple', 4),
        ('absurdist', config.VOICE_ARCHETYPES['absurdist']['name'], '幽默者', 'The Absurdist',
         config.VOICE_ARCHETYPES['absurdist']['systemPrompt'], 'masks', 'pink', 5),
    ]

    for voice_id, name, name_zh, name_en, prompt, icon, color, order in introspection_voices:
        db.execute("""
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt, icon, color, is_system, enabled, has_local_changes, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (voice_id, 'introspection_deck', name, name_zh, name_en, prompt, icon, color, 1, 1, order))

    # ========== Deck 2: Scholar Deck ==========
    db.execute("""
    INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en, icon, color, is_system, enabled, has_local_changes, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('scholar_deck', '学者卡组', '学者卡组', 'Scholar Deck',
          '从学术角度分析思考', '从学术角度分析思考', 'Analyze from academic perspectives',
          'lightbulb', 'blue', 1, 1, 0, 1))

    # Scholar voices (placeholder prompts - TODO: write detailed prompts)
    scholar_voices = [
        ('linguist', '语言学家', '语言学家', 'Linguist',
         'Analyze from linguistic structure, semantics, and pragmatics.', 'compass', 'blue', 0),
        ('painter', '画家', '画家', 'Painter',
         'Analyze from aesthetics, visual imagery, and mood.', 'eye', 'pink', 1),
        ('physicist', '物理学家', '物理学家', 'Physicist',
         'Analyze using physics laws, mechanics, and energy.', 'lightbulb', 'yellow', 2),
        ('computer_scientist', '计算机科学家', '计算机科学家', 'Computer Scientist',
         'Analyze using algorithms, data structures, and complexity.', 'brain', 'purple', 3),
        ('doctor', '医生', '医生', 'Doctor',
         'Analyze from medical, physiological, and psychological health perspectives.', 'heart', 'pink', 4),
        ('historian', '历史学家', '历史学家', 'Historian',
         'Provide historical context, cultural background, and patterns.', 'compass', 'green', 5),
    ]

    for voice_id, name, name_zh, name_en, prompt, icon, color, order in scholar_voices:
        db.execute("""
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt, icon, color, is_system, enabled, has_local_changes, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (voice_id, 'scholar_deck', name, name_zh, name_en, prompt, icon, color, 1, 1, order))

    # ========== Deck 3: Philosophy Deck ==========
    db.execute("""
    INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en, icon, color, is_system, enabled, has_local_changes, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('philosophy_deck', '哲学卡组', '哲学卡组', 'Philosophy Deck',
          '不同哲学流派的审视', '不同哲学流派的审视', 'Examine through philosophical lenses',
          'cloud', 'purple', 1, 1, 0, 2))

    # Philosophy voices (placeholder prompts - TODO: write detailed prompts)
    philosophy_voices = [
        ('stoic', '斯多葛派', '斯多葛派', 'Stoic',
         'Emphasize reason, self-control, and acceptance of the uncontrollable.', 'shield', 'blue', 0),
        ('taoist', '道家', '道家', 'Taoist',
         'Emphasize wu-wei (effortless action), natural flow, and simplicity.', 'wind', 'green', 1),
        ('existentialist', '存在主义者', '存在主义者', 'Existentialist',
         'Emphasize choice, freedom, responsibility, and creating meaning.', 'question', 'purple', 2),
        ('pragmatist', '实用主义者', '实用主义者', 'Pragmatist',
         'Focus on practical effects, usefulness, and real-world results.', 'fist', 'yellow', 3),
    ]

    for voice_id, name, name_zh, name_en, prompt, icon, color, order in philosophy_voices:
        db.execute("""
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt, icon, color, is_system, enabled, has_local_changes, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (voice_id, 'philosophy_deck', name, name_zh, name_en, prompt, icon, color, 1, 1, order))

    db.commit()
    db.close()
    print("✅ System decks seeded (3 decks, 16 voices)")

# ========== Deck CRUD ==========

def get_user_decks(user_id: int):
    """
    Get all user's own decks (forked from system templates).
    Returns list of deck dicts with voice counts.

    @@@ Users only see their own forked copies, never system decks directly
    """
    db = get_db()
    try:
        rows = db.execute("""
        SELECT d.*, COUNT(v.id) as voice_count
        FROM decks d
        LEFT JOIN voices v ON d.id = v.deck_id AND v.enabled = 1
        WHERE d.owner_id = ?
        GROUP BY d.id
        ORDER BY d.order_index, d.created_at
        """, (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()

def get_published_decks():
    """
    Get all published decks (community deck store).
    Returns list of deck dicts with voice counts and author info.
    """
    db = get_db()
    try:
        rows = db.execute("""
        SELECT d.*, COUNT(v.id) as voice_count, u.display_name as author_display_name
        FROM decks d
        LEFT JOIN voices v ON d.id = v.deck_id AND v.enabled = 1
        LEFT JOIN users u ON d.owner_id = u.id
        WHERE d.published = 1
        GROUP BY d.id
        ORDER BY d.install_count DESC, d.created_at DESC
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()

def publish_deck(deck_id: str, user_id: int):
    """
    Publish a deck to community store.
    @@@ Breaks parent chain - published deck becomes standalone
    """
    db = get_db()
    try:
        # Get user's display name for author_name
        user = db.execute("SELECT display_name FROM users WHERE id = ?", (user_id,)).fetchone()
        author_name = user['display_name'] if user and user['display_name'] else f"User {user_id}"

        db.execute("""
        UPDATE decks
        SET published = 1,
            author_name = ?,
            parent_id = NULL
        WHERE id = ? AND owner_id = ?
        """, (author_name, deck_id, user_id))
        db.commit()
    finally:
        db.close()

def unpublish_deck(deck_id: str, user_id: int):
    """
    Unpublish a deck from community store.
    """
    db = get_db()
    try:
        db.execute("""
        UPDATE decks
        SET published = 0
        WHERE id = ? AND owner_id = ?
        """, (deck_id, user_id))
        db.commit()
    finally:
        db.close()

def increment_deck_install_count(deck_id: str):
    """
    Increment install counter when deck is forked from store.
    """
    db = get_db()
    try:
        db.execute("""
        UPDATE decks
        SET install_count = install_count + 1
        WHERE id = ?
        """, (deck_id,))
        db.commit()
    finally:
        db.close()

def get_deck_with_voices(user_id: int, deck_id: str):
    """
    Get full deck details with all voices.
    Returns None if deck doesn't exist or user doesn't own it.

    @@@ Users only access their own forked decks
    """
    db = get_db()
    try:
        # Get deck (must be user's own)
        deck_row = db.execute("""
        SELECT * FROM decks
        WHERE id = ? AND owner_id = ?
        """, (deck_id, user_id)).fetchone()

        if not deck_row:
            return None

        deck = dict(deck_row)

        # Get voices in this deck
        voice_rows = db.execute("""
        SELECT * FROM voices
        WHERE deck_id = ?
        ORDER BY order_index, created_at
        """, (deck_id,)).fetchall()

        deck['voices'] = [dict(row) for row in voice_rows]
        return deck
    finally:
        db.close()

def create_deck(user_id: int, name: str, description: str = None,
                name_zh: str = None, name_en: str = None,
                description_zh: str = None, description_en: str = None,
                icon: str = None, color: str = None,
                order_index: int = None) -> str:
    """
    Create a new user deck. Returns deck_id.
    """
    import uuid

    db = get_db()
    try:
        deck_id = str(uuid.uuid4())

        # Get max order_index if not provided
        if order_index is None:
            max_order = db.execute(
                "SELECT MAX(order_index) as max_order FROM decks WHERE owner_id = ?",
                (user_id,)
            ).fetchone()['max_order']
            order_index = (max_order or 0) + 1

        db.execute("""
        INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en,
                          icon, color, is_system, owner_id, enabled, has_local_changes, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1, 0, ?)
        """, (deck_id, name, name_zh, name_en, description, description_zh, description_en,
              icon, color, user_id, order_index))

        db.commit()
        return deck_id
    finally:
        db.close()

def update_deck(user_id: int, deck_id: str, updates: dict) -> bool:
    """
    Update a user's deck. Only works if user owns the deck.
    Returns True if updated, False if not found or permission denied.

    Updates dict can contain: name, name_zh, name_en, description, description_zh,
    description_en, icon, color, enabled, order_index

    @@@ Content changes (name, description, icon, color) → has_local_changes = 1
    @@@ Preference changes (enabled, order_index) → don't affect has_local_changes
    """
    db = get_db()
    try:
        # Check ownership
        deck = db.execute(
            "SELECT owner_id FROM decks WHERE id = ?",
            (deck_id,)
        ).fetchone()

        if not deck or deck['owner_id'] != user_id:
            return False

        # Build update query
        allowed_fields = ['name', 'name_zh', 'name_en', 'description', 'description_zh',
                         'description_en', 'icon', 'color', 'enabled', 'order_index']
        content_fields = ['name', 'name_zh', 'name_en', 'description', 'description_zh',
                         'description_en', 'icon', 'color']

        update_fields = []
        params = []
        for field in allowed_fields:
            if field in updates:
                update_fields.append(f"{field} = ?")
                params.append(updates[field])

        if not update_fields:
            return True  # No updates

        # @@@ Mark as locally changed if content fields are modified
        has_content_change = any(field in updates for field in content_fields)
        if has_content_change:
            update_fields.append("has_local_changes = 1")

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(deck_id)

        db.execute(
            f"UPDATE decks SET {', '.join(update_fields)} WHERE id = ?",
            params
        )
        db.commit()
        return True
    finally:
        db.close()

def delete_deck(user_id: int, deck_id: str) -> bool:
    """
    Delete a user's deck. Only works if user owns the deck.
    Cascades to delete all voices in the deck.
    Returns True if deleted, False if not found or permission denied.
    """
    db = get_db()
    try:
        # Check ownership
        deck = db.execute(
            "SELECT owner_id FROM decks WHERE id = ?",
            (deck_id,)
        ).fetchone()

        if not deck or deck['owner_id'] != user_id:
            return False

        db.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        db.commit()
        return True
    finally:
        db.close()

def auto_fork_system_decks(user_id: int):
    """
    Auto-fork all system decks for a new user.
    Called on user registration/first login.
    """
    # @@@ Get deck list then close connection BEFORE forking (avoid deadlock)
    db = get_db()
    try:
        system_decks = db.execute(
            "SELECT id FROM decks WHERE is_system = 1 ORDER BY order_index"
        ).fetchall()
        deck_ids = [deck['id'] for deck in system_decks]
    finally:
        db.close()

    # Fork each deck (each fork opens its own connection)
    for deck_id in deck_ids:
        fork_deck(user_id, deck_id)

    print(f"✅ Auto-forked {len(deck_ids)} system decks for user {user_id}")

def fork_deck(user_id: int, deck_id: str) -> str:
    """
    Fork a deck to create user's own copy.
    Copies deck + all voices. Returns new deck_id.
    """
    import uuid

    db = get_db()
    try:
        # Get source deck
        source_deck = db.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        if not source_deck:
            raise ValueError(f"Deck {deck_id} not found")

        # Create new deck ID
        new_deck_id = str(uuid.uuid4())

        # Copy deck (has_local_changes = 0 initially, synced with parent)
        db.execute("""
        INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en,
                          icon, color, is_system, parent_id, owner_id, enabled, has_local_changes, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, 0, ?)
        """, (new_deck_id,
              source_deck['name'],
              source_deck['name_zh'],
              source_deck['name_en'],
              source_deck['description'],
              source_deck['description_zh'],
              source_deck['description_en'],
              source_deck['icon'],
              source_deck['color'],
              deck_id,  # parent_id tracks fork source
              user_id,
              source_deck['order_index']))

        # Copy all voices
        source_voices = db.execute(
            "SELECT * FROM voices WHERE deck_id = ? ORDER BY order_index",
            (deck_id,)
        ).fetchall()

        for voice in source_voices:
            new_voice_id = str(uuid.uuid4())
            db.execute("""
            INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt,
                              icon, color, is_system, parent_id, owner_id, enabled, has_local_changes, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, 0, ?)
            """, (new_voice_id,
                  new_deck_id,
                  voice['name'],
                  voice['name_zh'],
                  voice['name_en'],
                  voice['system_prompt'],
                  voice['icon'],
                  voice['color'],
                  voice['id'],  # parent_id tracks fork source
                  user_id,
                  voice['order_index']))

        db.commit()
        return new_deck_id
    finally:
        db.close()

def sync_deck_with_parent(user_id: int, deck_id: str, force: bool = False) -> dict:
    """
    Sync user's forked deck with parent template (complete reset).

    Deletes all user's voices and re-creates from parent template.
    This ensures deleted voices reappear and new parent voices are added.

    Returns: {"success": True, "synced_voices": N}
    Raises ValueError if deck not found, no parent, or parent missing
    """
    import uuid

    db = get_db()
    try:
        # Get user's deck
        deck = db.execute(
            "SELECT * FROM decks WHERE id = ? AND owner_id = ?",
            (deck_id, user_id)
        ).fetchone()

        if not deck:
            raise ValueError("Deck not found or permission denied")

        if not deck['parent_id']:
            raise ValueError("Deck is not a fork (no parent)")

        # Get parent deck
        parent = db.execute(
            "SELECT * FROM decks WHERE id = ?",
            (deck['parent_id'],)
        ).fetchone()

        if not parent:
            raise ValueError("Parent deck not found")

        # @@@ Step 1: Sync deck metadata (preserve user preferences like enabled/order)
        db.execute("""
        UPDATE decks SET
            name = ?, name_zh = ?, name_en = ?,
            description = ?, description_zh = ?, description_en = ?,
            icon = ?, color = ?,
            has_local_changes = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (parent['name'], parent['name_zh'], parent['name_en'],
              parent['description'], parent['description_zh'], parent['description_en'],
              parent['icon'], parent['color'],
              deck_id))

        # @@@ Step 2: Delete ALL user's voices in this deck
        db.execute("DELETE FROM voices WHERE deck_id = ?", (deck_id,))

        # @@@ Step 3: Re-create all voices from parent (fresh copy)
        parent_voices = db.execute(
            "SELECT * FROM voices WHERE deck_id = ? ORDER BY order_index",
            (deck['parent_id'],)
        ).fetchall()

        synced_count = 0
        for parent_voice in parent_voices:
            new_voice_id = str(uuid.uuid4())
            db.execute("""
            INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt,
                              icon, color, is_system, parent_id, owner_id, enabled, has_local_changes, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, 0, ?)
            """, (new_voice_id,
                  deck_id,  # User's deck
                  parent_voice['name'],
                  parent_voice['name_zh'],
                  parent_voice['name_en'],
                  parent_voice['system_prompt'],
                  parent_voice['icon'],
                  parent_voice['color'],
                  parent_voice['id'],  # parent_id tracks original
                  user_id,
                  parent_voice['order_index']))
            synced_count += 1

        db.commit()
        return {"success": True, "synced_voices": synced_count}
    finally:
        db.close()

def load_voices_from_user_decks(user_id: int) -> dict:
    """
    Load all enabled voices from user's enabled decks for LLM analysis.

    Returns dict format: {voice_id: {name, systemPrompt, icon, color}}
    Compatible with analyze_stateless() expectations.
    """
    db = get_db()
    try:
        # Get all user's enabled decks
        enabled_decks = db.execute("""
        SELECT id FROM decks
        WHERE owner_id = ? AND enabled = 1
        ORDER BY order_index, created_at
        """, (user_id,)).fetchall()

        if not enabled_decks:
            return {}

        deck_ids = [deck['id'] for deck in enabled_decks]

        # Get all enabled voices from these decks
        placeholders = ','.join('?' * len(deck_ids))
        voices = db.execute(f"""
        SELECT id, name, system_prompt, icon, color
        FROM voices
        WHERE deck_id IN ({placeholders}) AND enabled = 1
        ORDER BY order_index, created_at
        """, deck_ids).fetchall()

        # Convert to expected format
        voice_dict = {}
        for voice in voices:
            voice_dict[voice['id']] = {
                'name': voice['name'],
                'systemPrompt': voice['system_prompt'],
                'icon': voice['icon'],
                'color': voice['color']
            }

        return voice_dict
    finally:
        db.close()

# ========== Voice CRUD ==========

def create_voice(user_id: int, deck_id: str, name: str, system_prompt: str,
                name_zh: str = None, name_en: str = None,
                icon: str = None, color: str = None,
                order_index: int = None) -> str:
    """
    Create a new voice in a user's deck.
    Returns voice_id.
    """
    import uuid

    db = get_db()
    try:
        # Check deck ownership
        deck = db.execute(
            "SELECT owner_id FROM decks WHERE id = ?",
            (deck_id,)
        ).fetchone()

        if not deck or deck['owner_id'] != user_id:
            raise ValueError("Deck not found or permission denied")

        voice_id = str(uuid.uuid4())

        # Get max order_index if not provided
        if order_index is None:
            max_order = db.execute(
                "SELECT MAX(order_index) as max_order FROM voices WHERE deck_id = ?",
                (deck_id,)
            ).fetchone()['max_order']
            order_index = (max_order or 0) + 1

        db.execute("""
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt,
                           icon, color, is_system, owner_id, enabled, has_local_changes, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1, 0, ?)
        """, (voice_id, deck_id, name, name_zh, name_en, system_prompt,
              icon, color, user_id, order_index))

        db.commit()
        return voice_id
    finally:
        db.close()

def update_voice(user_id: int, voice_id: str, updates: dict) -> bool:
    """
    Update a user's voice. Only works if user owns the voice.
    Returns True if updated, False if not found or permission denied.

    Updates dict can contain: name, name_zh, name_en, system_prompt,
    icon, color, enabled, order_index

    @@@ Content changes (name, system_prompt, icon, color) → has_local_changes = 1
    @@@ Preference changes (enabled, order_index) → don't affect has_local_changes
    """
    db = get_db()
    try:
        # Check ownership
        voice = db.execute(
            "SELECT owner_id FROM voices WHERE id = ?",
            (voice_id,)
        ).fetchone()

        if not voice or voice['owner_id'] != user_id:
            return False

        # Build update query
        allowed_fields = ['name', 'name_zh', 'name_en', 'system_prompt',
                         'icon', 'color', 'enabled', 'order_index']
        content_fields = ['name', 'name_zh', 'name_en', 'system_prompt',
                         'icon', 'color']

        update_fields = []
        params = []
        for field in allowed_fields:
            if field in updates:
                update_fields.append(f"{field} = ?")
                params.append(updates[field])

        if not update_fields:
            return True  # No updates

        # @@@ Mark as locally changed if content fields are modified
        has_content_change = any(field in updates for field in content_fields)
        if has_content_change:
            update_fields.append("has_local_changes = 1")

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(voice_id)

        db.execute(
            f"UPDATE voices SET {', '.join(update_fields)} WHERE id = ?",
            params
        )
        db.commit()
        return True
    finally:
        db.close()

def delete_voice(user_id: int, voice_id: str) -> bool:
    """
    Delete a user's voice. Only works if user owns the voice.
    Returns True if deleted, False if not found or permission denied.
    """
    db = get_db()
    try:
        # Check ownership
        voice = db.execute(
            "SELECT owner_id FROM voices WHERE id = ?",
            (voice_id,)
        ).fetchone()

        if not voice or voice['owner_id'] != user_id:
            return False

        db.execute("DELETE FROM voices WHERE id = ?", (voice_id,))
        db.commit()
        return True
    finally:
        db.close()

def fork_voice(user_id: int, voice_id: str, target_deck_id: str) -> str:
    """
    Fork a voice to a user's deck.
    Returns new voice_id.
    """
    import uuid

    db = get_db()
    try:
        # Check target deck ownership
        deck = db.execute(
            "SELECT owner_id FROM decks WHERE id = ?",
            (target_deck_id,)
        ).fetchone()

        if not deck or deck['owner_id'] != user_id:
            raise ValueError("Target deck not found or permission denied")

        # Get source voice
        source_voice = db.execute("SELECT * FROM voices WHERE id = ?", (voice_id,)).fetchone()
        if not source_voice:
            raise ValueError(f"Voice {voice_id} not found")

        # Create new voice
        new_voice_id = str(uuid.uuid4())

        # Get max order_index in target deck
        max_order = db.execute(
            "SELECT MAX(order_index) as max_order FROM voices WHERE deck_id = ?",
            (target_deck_id,)
        ).fetchone()['max_order']
        order_index = (max_order or 0) + 1

        db.execute("""
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt,
                           icon, color, is_system, parent_id, owner_id, enabled, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, ?)
        """, (new_voice_id,
              target_deck_id,
              source_voice['name'],
              source_voice['name_zh'],
              source_voice['name_en'],
              source_voice['system_prompt'],
              source_voice['icon'],
              source_voice['color'],
              voice_id,  # parent_id tracks fork source
              user_id,
              order_index))

        db.commit()
        return new_voice_id
    finally:
        db.close()

# ========== User Management ==========

def create_user(email: str, password_hash: str, display_name: str = None) -> int:
    """Create a new user. Returns user_id."""
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
            (email, password_hash, display_name)
        )
        user_id = cursor.lastrowid
        db.commit()
        return user_id
    except sqlite3.IntegrityError:
        raise ValueError("Email already exists")
    finally:
        db.close()

def get_user_by_email(email: str):
    """Get user by email. Returns dict or None."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, email, password_hash, display_name, created_at FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()

def get_user_by_id(user_id: int):
    """Get user by ID. Returns dict or None."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()

# ========== Session Storage ==========

def save_session(user_id: int, session_id: str, editor_state: dict, name: str = None):
    """Save or update a user session."""
    db = get_db()
    try:
        db.execute("""
        INSERT INTO user_sessions (id, user_id, name, editor_state_json, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          editor_state_json = excluded.editor_state_json,
          name = COALESCE(excluded.name, name),
          updated_at = CURRENT_TIMESTAMP
        """, (session_id, user_id, name, json.dumps(editor_state)))
        db.commit()
    finally:
        db.close()

def get_session(user_id: int, session_id: str):
    """Get a specific session. Returns dict or None."""
    db = get_db()
    try:
        row = db.execute("""
        SELECT id, name, editor_state_json, created_at, updated_at
        FROM user_sessions
        WHERE user_id = ? AND id = ?
        """, (user_id, session_id)).fetchone()

        if row:
            result = dict(row)
            result['editor_state'] = json.loads(result['editor_state_json'])
            del result['editor_state_json']
            return result
        return None
    finally:
        db.close()

def list_sessions(user_id: int):
    """List all sessions for a user."""
    db = get_db()
    try:
        rows = db.execute("""
        SELECT id, name, created_at, updated_at
        FROM user_sessions
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """, (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()

def delete_session(user_id: int, session_id: str):
    """Delete a session."""
    db = get_db()
    try:
        db.execute("DELETE FROM user_sessions WHERE user_id = ? AND id = ?", (user_id, session_id))
        db.commit()
    finally:
        db.close()

# ========== Timeline Auto-Generation Helpers ==========

def get_users_with_activity_on_date(target_date: str, timezone: str = 'Asia/Shanghai') -> list[int]:
    """
    Get user IDs who updated sessions on target_date (local timezone).

    Args:
        target_date: Date string in YYYY-MM-DD format (local timezone)
        timezone: Timezone name (default: Asia/Shanghai for Beijing)

    Returns:
        List of user_ids with non-empty sessions on that date

    @@@ Timezone handling - SQLite stores UTC, we convert to local timezone for date matching
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    db = get_db()
    try:
        # @@@ Convert target_date (local) to UTC range for database query
        # Example: 2025-01-17 in Beijing = 2025-01-16 16:00 UTC to 2025-01-17 16:00 UTC
        tz = ZoneInfo(timezone)
        local_date = datetime.strptime(target_date, '%Y-%m-%d').replace(tzinfo=tz)

        # Get start and end of day in UTC
        start_of_day_local = local_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day_local = local_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        start_utc = start_of_day_local.astimezone(ZoneInfo('UTC'))
        end_utc = end_of_day_local.astimezone(ZoneInfo('UTC'))

        # Query sessions updated in this UTC range
        rows = db.execute("""
            SELECT DISTINCT user_id, editor_state_json
            FROM user_sessions
            WHERE updated_at >= ? AND updated_at <= ?
        """, (start_utc.isoformat(), end_utc.isoformat())).fetchall()

        # Filter users with non-empty content
        user_ids = []
        for row in rows:
            try:
                state = json.loads(row['editor_state_json'])
                # Check if has any text cells with content
                has_content = any(
                    cell.get('type') == 'text' and cell.get('content', '').strip()
                    for cell in state.get('cells', [])
                )
                if has_content and row['user_id'] not in user_ids:
                    user_ids.append(row['user_id'])
            except (json.JSONDecodeError, KeyError):
                continue

        return user_ids
    finally:
        db.close()

def extract_text_from_sessions_on_date(user_id: int, target_date: str, timezone: str = 'Asia/Shanghai') -> str:
    """
    Extract all text from user's sessions updated on target_date (local timezone).

    Args:
        user_id: User ID
        target_date: Date string in YYYY-MM-DD format (local timezone)
        timezone: Timezone name (default: Asia/Shanghai for Beijing)

    Returns:
        Concatenated text from all text cells, joined with double newlines

    @@@ Replicates frontend's getAllNotesFromSessions() logic but date-filtered
    @@@ Timezone handling - SQLite stores UTC, we convert to local timezone for date matching
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    db = get_db()
    try:
        # @@@ Convert target_date (local) to UTC range for database query
        tz = ZoneInfo(timezone)
        local_date = datetime.strptime(target_date, '%Y-%m-%d').replace(tzinfo=tz)

        start_of_day_local = local_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day_local = local_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        start_utc = start_of_day_local.astimezone(ZoneInfo('UTC'))
        end_utc = end_of_day_local.astimezone(ZoneInfo('UTC'))

        # Get sessions updated in this UTC range
        rows = db.execute("""
            SELECT editor_state_json
            FROM user_sessions
            WHERE user_id = ?
              AND updated_at >= ?
              AND updated_at <= ?
            ORDER BY updated_at DESC
        """, (user_id, start_utc.isoformat(), end_utc.isoformat())).fetchall()

        # Extract text from each session
        all_text = []
        for row in rows:
            try:
                state = json.loads(row['editor_state_json'])
                # @@@ Same logic as frontend: filter text cells, extract content
                text = '\n\n'.join(
                    cell['content']
                    for cell in state.get('cells', [])
                    if cell.get('type') == 'text' and cell.get('content', '').strip()
                )
                if text.strip():
                    all_text.append(text)
            except (json.JSONDecodeError, KeyError):
                continue

        return '\n\n'.join(all_text)
    finally:
        db.close()

# ========== Daily Pictures ==========

def save_daily_picture(user_id: int, date: str, image_base64: str, prompt: str = None, thumbnail_base64: str = None):
    """Save daily picture (replaces any existing picture for this user+date)."""
    db = get_db()
    try:
        # @@@ Delete old pictures for this user+date combination first
        # This ensures only ONE picture per day while avoiding UNIQUE constraint timezone issues
        db.execute("""
        DELETE FROM daily_pictures
        WHERE user_id = ? AND date = ?
        """, (user_id, date))

        # Insert the new picture
        db.execute("""
        INSERT INTO daily_pictures (user_id, date, image_base64, thumbnail_base64, prompt)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, date, image_base64, thumbnail_base64, prompt))

        db.commit()
    finally:
        db.close()

def get_daily_pictures(user_id: int, limit: int = 30):
    """Get recent daily pictures (returns ONLY thumbnails for fast timeline loading)."""
    db = get_db()
    try:
        # @@@ Use COALESCE to return thumbnail, fallback to full image only if needed
        # This prevents loading full images when thumbnails exist
        rows = db.execute("""
        SELECT date, COALESCE(thumbnail_base64, image_base64) as base64, prompt, created_at
        FROM daily_pictures
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT ?
        """, (user_id, limit)).fetchall()
        return [{
            'date': row['date'],
            'base64': row['base64'],
            'prompt': row['prompt'] or '',
            'created_at': row['created_at']
        } for row in rows]
    finally:
        db.close()

def get_daily_picture_full(user_id: int, date: str):
    """Get full resolution image for a specific date (on-demand loading)."""
    db = get_db()
    try:
        row = db.execute("""
        SELECT image_base64
        FROM daily_pictures
        WHERE user_id = ? AND date = ?
        ORDER BY created_at DESC
        LIMIT 1
        """, (user_id, date)).fetchone()

        if row:
            return row['image_base64']
        return None
    finally:
        db.close()

# ========== User Preferences ==========

def save_preferences(user_id: int, voice_configs: dict = None, meta_prompt: str = None,
                    state_config: dict = None, selected_state: str = None):
    """Save or update user preferences."""
    db = get_db()
    try:
        # Check if preferences exist
        existing = db.execute("SELECT user_id FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()

        if existing:
            # Update
            updates = []
            params = []
            if voice_configs is not None:
                updates.append("voice_configs_json = ?")
                params.append(json.dumps(voice_configs))
            if meta_prompt is not None:
                updates.append("meta_prompt = ?")
                params.append(meta_prompt)
            if state_config is not None:
                updates.append("state_config_json = ?")
                params.append(json.dumps(state_config))
            if selected_state is not None:
                updates.append("selected_state = ?")
                params.append(selected_state)

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(user_id)
                db.execute(f"UPDATE user_preferences SET {', '.join(updates)} WHERE user_id = ?", params)
        else:
            # Insert
            db.execute("""
            INSERT INTO user_preferences (user_id, voice_configs_json, meta_prompt, state_config_json, selected_state)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id,
                  json.dumps(voice_configs) if voice_configs else None,
                  meta_prompt,
                  json.dumps(state_config) if state_config else None,
                  selected_state))

        db.commit()
    finally:
        db.close()

def get_preferences(user_id: int):
    """Get user preferences. Returns dict or None."""
    db = get_db()
    try:
        row = db.execute("""
        SELECT voice_configs_json, meta_prompt, state_config_json, selected_state,
               first_login_completed, updated_at
        FROM user_preferences
        WHERE user_id = ?
        """, (user_id,)).fetchone()

        if row:
            result = dict(row)
            result['voice_configs'] = json.loads(result['voice_configs_json']) if result['voice_configs_json'] else None
            result['state_config'] = json.loads(result['state_config_json']) if result['state_config_json'] else None
            del result['voice_configs_json']
            del result['state_config_json']
            return result
        return None
    finally:
        db.close()

def set_first_login_completed(user_id: int):
    """Mark user's first login as completed."""
    db = get_db()
    try:
        # Check if preferences exist
        existing = db.execute("SELECT user_id FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()

        if existing:
            # Update existing
            db.execute("""
            UPDATE user_preferences
            SET first_login_completed = 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """, (user_id,))
        else:
            # Insert new
            db.execute("""
            INSERT INTO user_preferences (user_id, first_login_completed)
            VALUES (?, 1)
            """, (user_id,))

        db.commit()
    finally:
        db.close()

# ========== Analysis Reports ==========

def save_analysis_report(user_id: int, report_type: str, report_data: dict, all_notes_text: str = None):
    """Save an analysis report."""
    db = get_db()
    try:
        db.execute("""
        INSERT INTO analysis_reports (user_id, report_type, report_data_json, all_notes_text)
        VALUES (?, ?, ?, ?)
        """, (user_id, report_type, json.dumps(report_data), all_notes_text))
        db.commit()
    finally:
        db.close()

def get_analysis_reports(user_id: int, limit: int = 10):
    """Get recent analysis reports."""
    db = get_db()
    try:
        rows = db.execute("""
        SELECT id, report_type, report_data_json, created_at
        FROM analysis_reports
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """, (user_id, limit)).fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result['report_data'] = json.loads(result['report_data_json'])
            del result['report_data_json']
            results.append(result)
        return results
    finally:
        db.close()

# ========== Bulk Import (for localStorage migration) ==========

def import_user_data(user_id: int, sessions: list, pictures: list, preferences: dict, reports: list = None):
    """
    Bulk import user data from localStorage migration.

    Args:
        user_id: User ID
        sessions: List of {id, name, editor_state}
        pictures: List of {date, image_base64, prompt}
        preferences: {voice_configs, meta_prompt, state_config, selected_state}
        reports: Optional list of {type, data, allNotes, timestamp}
    """
    db = get_db()
    try:
        # Import sessions
        for session in sessions:
            db.execute("""
            INSERT OR REPLACE INTO user_sessions (id, user_id, name, editor_state_json)
            VALUES (?, ?, ?, ?)
            """, (session['id'], user_id, session.get('name'), json.dumps(session['editor_state'])))

        # Import pictures
        for picture in pictures:
            db.execute("""
            INSERT OR REPLACE INTO daily_pictures (user_id, date, image_base64, prompt)
            VALUES (?, ?, ?, ?)
            """, (user_id, picture['date'], picture['image_base64'], picture.get('prompt')))

        # Import preferences
        if preferences:
            db.execute("""
            INSERT OR REPLACE INTO user_preferences
            (user_id, voice_configs_json, meta_prompt, state_config_json, selected_state)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id,
                  json.dumps(preferences.get('voice_configs')) if preferences.get('voice_configs') else None,
                  preferences.get('meta_prompt'),
                  json.dumps(preferences.get('state_config')) if preferences.get('state_config') else None,
                  preferences.get('selected_state')))

        # Import analysis reports
        if reports:
            for report in reports:
                db.execute("""
                INSERT INTO analysis_reports (user_id, report_type, report_data_json, all_notes_text)
                VALUES (?, ?, ?, ?)
                """, (user_id, report.get('type', 'unknown'), json.dumps(report.get('data', {})), report.get('allNotes')))

        db.commit()
        print(f"✅ Imported {len(sessions)} sessions, {len(pictures)} pictures, {len(reports or [])} reports for user {user_id}")
    finally:
        db.close()

if __name__ == "__main__":
    # Initialize database
    init_db()
