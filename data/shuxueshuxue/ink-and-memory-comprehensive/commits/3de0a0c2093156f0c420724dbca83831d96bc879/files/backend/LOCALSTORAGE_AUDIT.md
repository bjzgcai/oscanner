# localStorage Audit - Complete Data Inventory

## All localStorage Keys Currently Used

### 1. **Editor State** (CRITICAL)
- **Key**: `ink_memory_state`
- **Location**: `App.tsx`
- **Content**: Full EditorState (cells, commentors, current session)
- **Size**: ~50-200KB per session
- **Migration**: ✅ Save to `user_sessions` table

### 2. **Calendar Entries** (CRITICAL)
- **Key**: `calendar-entries`
- **Location**: `calendarStorage.ts`
- **Content**: `{ "YYYY-MM-DD": [{ id, timestamp, state, firstLine }] }`
- **Size**: Can be LARGE (multiple full EditorStates)
- **Migration**: ✅ Extract each entry and save as separate session in `user_sessions`

### 3. **Daily Pictures** (CRITICAL - QUOTA PROBLEM!)
- **Key**: `daily-pictures`
- **Location**: `CollectionsView.tsx`
- **Content**: `[{ date, base64, prompt }]`
- **Size**: **1.5MB per image** ← This is why we need database!
- **Migration**: ✅ Save to `daily_pictures` table

### 4. **Voice Customizations**
- **Key**: `voice-customizations`
- **Location**: `voiceStorage.ts`
- **Content**: `{ [voiceKey]: { name, tagline, icon, color, enabled } }`
- **Size**: ~5-20KB
- **Migration**: ✅ Save to `user_preferences.voice_configs_json`

### 5. **Meta Prompt**
- **Key**: `meta-prompt`
- **Location**: `voiceStorage.ts`
- **Content**: String (global instructions for all voices)
- **Size**: ~1-5KB
- **Migration**: ✅ Save to `user_preferences.meta_prompt`

### 6. **State Config**
- **Key**: `state-config`
- **Location**: `voiceStorage.ts`
- **Content**: `{ greeting, states: { happy: {name, prompt}, ... } }`
- **Size**: ~2-10KB
- **Migration**: ✅ Save to `user_preferences.state_config_json`

### 7. **Selected State**
- **Key**: `selected-state`
- **Location**: `App.tsx`
- **Content**: String (e.g., "happy", "ok", "unhappy")
- **Size**: ~10 bytes
- **Migration**: ✅ Save to `user_preferences.selected_state`

### 8. **Analysis Reports History**
- **Key**: `analysis-reports-history`
- **Location**: `AnalysisView.tsx`
- **Content**: `[{ timestamp, type, data, allNotes }]`
- **Size**: ~10-50KB (limited to 10 reports)
- **Migration**: ⚠️ **MISSING FROM DATABASE!** Need new table

### 9. **Document Storage** (OLD SYSTEM - probably unused?)
- **Key**: `ink_and_memory_document`
- **Location**: `documentStorage.ts`
- **Content**: `{ document, conversations, lastModified }`
- **Size**: Unknown
- **Migration**: ⚠️ **Check if this is still used** - might be deprecated

## Database Schema Gaps Found

### ❌ Missing Table: `analysis_reports`
```sql
CREATE TABLE analysis_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  report_type TEXT NOT NULL,  -- 'echoes', 'traits', 'patterns'
  report_data_json TEXT NOT NULL,
  all_notes_text TEXT,  -- The text that was analyzed
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

### ❌ Missing: Calendar Entry Handling
- Calendar entries contain full EditorStates
- Need to extract each calendar entry as a separate session
- Need to preserve `date` and `timestamp` metadata

## Migration Strategy

### Phase 1: On First Login (Auto-Migration)
```javascript
async function migrateLocalStorageToServer() {
  const migrationData = {
    // Current session
    currentSession: localStorage.getItem('ink_memory_state'),

    // Calendar entries (extract as separate sessions)
    calendarEntries: localStorage.getItem('calendar-entries'),

    // Pictures (THE BIG ONE!)
    dailyPictures: localStorage.getItem('daily-pictures'),

    // Preferences
    voiceCustomizations: localStorage.getItem('voice-customizations'),
    metaPrompt: localStorage.getItem('meta-prompt'),
    stateConfig: localStorage.getItem('state-config'),
    selectedState: localStorage.getItem('selected-state'),

    // Reports
    analysisReports: localStorage.getItem('analysis-reports-history'),

    // Old document storage (check if used)
    oldDocument: localStorage.getItem('ink_and_memory_document')
  };

  // POST to /api/import-local-data
  await fetch('/api/import-local-data', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: JSON.stringify(migrationData)
  });

  // Clear localStorage (keep only auth token)
  clearLocalStorage();
}
```

### Phase 2: Server-First Operation
After migration:
- localStorage only stores: auth token
- All data fetched from server on load
- Auto-save to server every 30s

## Size Estimates

**Typical user localStorage usage:**
- Current session: ~100KB
- Calendar entries (30 days): ~3MB (30 sessions × 100KB)
- Daily pictures (7 days): **10.5MB** ← EXCEEDS QUOTA!
- Preferences: ~30KB
- Reports: ~50KB
- **TOTAL: ~13.7MB** ← Way over 5-10MB limit!

**With database:**
- localStorage: ~1KB (just token)
- SQLite: Unlimited (file-based)

## Action Items

1. ✅ Add `analysis_reports` table to database schema
2. ✅ Update `import_user_data()` to handle:
   - Calendar entries extraction
   - Analysis reports
   - Old document storage check
3. ✅ Create comprehensive migration endpoint `/api/import-local-data`
4. ⚠️ Test migration with real localStorage data
5. ⚠️ Add data validation (check JSON parsing before import)
