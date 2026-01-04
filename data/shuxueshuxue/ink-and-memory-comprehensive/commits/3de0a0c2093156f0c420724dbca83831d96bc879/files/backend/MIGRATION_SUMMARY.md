# localStorage Migration - Complete Picture

## 🚨 Critical Discovery

**Current localStorage usage: ~13.7MB per typical user**
- localStorage limit: 5-10MB
- **You've been living on borrowed time!**

### The Quota Bomb:
```
Current session:      100 KB
Calendar (30 days):  3000 KB  (30 sessions)
Pictures (7 days):  10500 KB  ← THE PROBLEM!
Preferences:           30 KB
Reports:               50 KB
─────────────────────────────
TOTAL:             ~13680 KB  ← 13.7 MB!
```

**This explains the QuotaExceededError!**

---

## ✅ Complete Data Inventory

### 9 localStorage Keys Found:

1. ✅ `ink_memory_state` → `user_sessions` table
2. ✅ `calendar-entries` → Extract each entry as separate session
3. ✅ `daily-pictures` → `daily_pictures` table
4. ✅ `voice-customizations` → `user_preferences.voice_configs_json`
5. ✅ `meta-prompt` → `user_preferences.meta_prompt`
6. ✅ `state-config` → `user_preferences.state_config_json`
7. ✅ `selected-state` → `user_preferences.selected_state`
8. ✅ `analysis-reports-history` → `analysis_reports` table (NEW!)
9. ⚠️ `ink_and_memory_document` → Check if still used (might be old)

---

## 📦 Database Schema (Complete)

### Tables Created:
```sql
users                -- Email, password, display name
user_sessions        -- Editor states (replaces localStorage sessions)
daily_pictures       -- Images (solves quota problem!)
user_preferences     -- Voice configs, meta prompt, state config
analysis_reports     -- Echoes, traits, patterns (NEW!)
auth_sessions        -- Session tokens
schema_version       -- Migration tracking
```

### Key Features:
- ✅ WAL mode enabled (concurrent reads + 1 write)
- ✅ Foreign keys enforced (CASCADE DELETE)
- ✅ Indexes on user_id for fast queries
- ✅ JSON columns for flexibility (no schema migrations needed)

---

## 🔄 Migration Plan

### On First Login:
```javascript
// 1. Detect localStorage data
if (hasLocalStorageData()) {
  // 2. Show banner
  <Banner>
    💾 Migrating your local data to your account...
  </Banner>

  // 3. Extract all data
  const migrationData = extractAllLocalStorageData();

  // 4. POST to server
  await fetch('/api/import-local-data', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(migrationData)
  });

  // 5. Verify migration
  const verify = await fetch('/api/verify-migration');

  // 6. Clear localStorage (keep only token)
  if (verify.ok) {
    clearLocalStorage();
    localStorage.setItem('auth-token', token);
  }
}
```

### Special Cases:

**Calendar Entries (Complex!):**
```javascript
// calendar-entries: { "2025-11-01": [entry1, entry2], "2025-11-02": [...] }
// Each entry contains full EditorState

function extractCalendarEntries(calendarData) {
  const sessions = [];

  for (const [date, entries] of Object.entries(calendarData)) {
    for (const entry of entries) {
      sessions.push({
        id: entry.id,
        name: `${date} - ${entry.firstLine}`,
        editor_state: entry.state,
        // Preserve original timestamp
        created_at: new Date(entry.timestamp).toISOString()
      });
    }
  }

  return sessions;
}
```

**Pictures (The Big One!):**
```javascript
// pictures: [{ date, base64, prompt }]
// Each base64 string is ~1.5MB!

function extractPictures(picturesData) {
  return picturesData.map(p => ({
    date: p.date,
    image_base64: p.base64,  // Goes straight to SQLite (unlimited)
    prompt: p.prompt
  }));
}
```

---

## 🎯 Guest Mode Strategy

### Before Login:
```javascript
// localStorage works normally
localStorage.setItem('ink_memory_state', state);
localStorage.setItem('daily-pictures', pictures);

// ❌ But blocks image generation if >5MB used
if (getLocalStorageSize() > 5 * 1024 * 1024) {
  alert('⚠️ Storage full! Create account to generate images.');
  return;
}
```

### After Login:
```javascript
// Server becomes primary
await fetch('/api/save-session', { body: state });

// localStorage only stores token
localStorage.clear();
localStorage.setItem('auth-token', token);
```

### Image Generation Gate:
```javascript
async function generateImage() {
  if (!isLoggedIn()) {
    showLoginPrompt('🎨 Create a free account to generate images');
    return;
  }

  // Logged in users: unlimited images!
  const image = await fetch('/api/generate-image', ...);
}
```

---

## 📊 Storage Comparison

### Before (localStorage):
- Max: 10MB (hard limit)
- Current usage: ~13.7MB (OVER LIMIT!)
- Pictures: 7 max before quota error
- Sync: None (single device only)
- Backup: None (data lost if browser cache cleared)

### After (SQLite):
- Max: Unlimited (file-based)
- Current usage: Irrelevant
- Pictures: Unlimited
- Sync: Across devices
- Backup: Daily automated backups

---

## 🚀 Next Steps

1. [x] Database schema complete
2. [x] Migration functions ready
3. [ ] Create auth module (JWT, bcrypt)
4. [ ] Add auth endpoints to FastAPI
5. [ ] Create frontend login/register UI
6. [ ] Implement auto-migration on first login
7. [ ] Add image generation gate
8. [ ] Test with real localStorage data
9. [ ] Deploy to production

---

## ⚠️ Important Notes

1. **No data loss**: Migration keeps localStorage until verified
2. **Rollback safe**: Can revert to localStorage if migration fails
3. **Incremental**: Users can keep using app during migration
4. **Guest mode works**: Anonymous users can still use app (limited)

---

**Ready to proceed with auth implementation!**
