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
      order_index INTEGER,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (parent_id) REFERENCES decks(id),
      FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_decks_owner ON decks(owner_id)")

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
    INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en, icon, color, is_system, enabled, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('introspection_deck', '内省卡组', '内省卡组', 'Introspection Deck',
          '内心对话原型', '内心对话原型', 'Inner dialogue archetypes',
          'brain', 'purple', 1, 1, 0))

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
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt, icon, color, is_system, enabled, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (voice_id, 'introspection_deck', name, name_zh, name_en, prompt, icon, color, 1, 1, order))

    # ========== Deck 2: Scholar Deck ==========
    db.execute("""
    INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en, icon, color, is_system, enabled, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('scholar_deck', '学者卡组', '学者卡组', 'Scholar Deck',
          '从学术角度分析思考', '从学术角度分析思考', 'Analyze from academic perspectives',
          'lightbulb', 'blue', 1, 1, 1))

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
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt, icon, color, is_system, enabled, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (voice_id, 'scholar_deck', name, name_zh, name_en, prompt, icon, color, 1, 1, order))

    # ========== Deck 3: Philosophy Deck ==========
    db.execute("""
    INSERT INTO decks (id, name, name_zh, name_en, description, description_zh, description_en, icon, color, is_system, enabled, order_index)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('philosophy_deck', '哲学卡组', '哲学卡组', 'Philosophy Deck',
          '不同哲学流派的审视', '不同哲学流派的审视', 'Examine through philosophical lenses',
          'cloud', 'purple', 1, 1, 2))

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
        INSERT INTO voices (id, deck_id, name, name_zh, name_en, system_prompt, icon, color, is_system, enabled, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (voice_id, 'philosophy_deck', name, name_zh, name_en, prompt, icon, color, 1, 1, order))

    db.commit()
    db.close()
    print("✅ System decks seeded (3 decks, 16 voices)")

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
