// App.tsx
import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { Commentor, EditorState, TextCell } from './engine/EditorEngine';
import { ChatWidget } from './engine/ChatWidget';
import type { ChatWidgetData } from './engine/ChatWidget';
import './App.css';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass,
  FaPenNib, FaRegClock, FaChartBar, FaLayerGroup, FaCog,
} from 'react-icons/fa';
import TopNavBar from './components/TopNavBar';
import LeftToolbar from './components/LeftToolbar';
import DeckManager from './components/DeckManager';
import CalendarPopup from './components/CalendarPopup';
import { type CalendarEntry } from './utils/calendarStorage';
import CollectionsView from './components/CollectionsView';
import AnalysisView from './components/AnalysisView';
import AboutView from './components/AboutView';
import AgentDropdown from './components/AgentDropdown';
import ChatWidgetUI from './components/ChatWidgetUI';
import StateChooser from './components/StateChooser';
import type { VoiceConfig } from './api/voiceApi';
import { getVoices, getMetaPrompt, getStateConfig } from './utils/voiceStorage';
import { getDefaultVoices, chatWithVoice, importLocalData, loadVoicesFromDecks } from './api/voiceApi';
import { useMobile } from './utils/mobileDetect';
import { CommentGroupCard } from './components/CommentCard';
import { findNormalizedPhrase } from './utils/textNormalize';
import { useAuth } from './contexts/AuthContext';
import LoginForm from './components/Auth/LoginForm';
import RegisterForm from './components/Auth/RegisterForm';
import { STORAGE_KEYS } from './constants/storageKeys';
import { getLocalDayKey, getTodayKeyInTimezone } from './utils/timezone';
import { useSessionLifecycle } from './hooks/useSessionLifecycle';
import { useInspiration } from './hooks/useInspiration';
import { InspirationHint } from './components/Editor/InspirationHint';
import { useComments } from './hooks/useComments';
import { useTextCells } from './hooks/useTextCells';
import { useVoiceInput } from './hooks/useVoiceInput';

// @@@ Icon map with React Icons
const iconMap = {
  brain: FaBrain,
  heart: FaHeart,
  question: FaQuestion,
  cloud: FaCloud,
  masks: FaTheaterMasks,
  eye: FaEye,
  fist: FaFistRaised,
  lightbulb: FaLightbulb,
  shield: FaShieldAlt,
  wind: FaWind,
  fire: FaFire,
  compass: FaCompass,
};

const LANGUAGE_CODES: Array<'en' | 'zh'> = ['en', 'zh'];

// @@@ Color map with gradient colors for watercolor effect
const colorMap: Record<string, { gradient: string; text: string; glow: string }> = {
  blue: {
    gradient: 'linear-gradient(90deg, rgba(77,159,255,0) 0%, rgba(77,159,255,0.05) 30%, rgba(77,159,255,0.12) 60%, rgba(77,159,255,0.25) 100%)',
    text: '#0066cc',
    glow: 'rgba(77,159,255,0.15)'
  },
  pink: {
    gradient: 'linear-gradient(90deg, rgba(255,102,179,0) 0%, rgba(255,102,179,0.05) 30%, rgba(255,102,179,0.12) 60%, rgba(255,102,179,0.25) 100%)',
    text: '#cc0066',
    glow: 'rgba(255,102,179,0.15)'
  },
  yellow: {
    gradient: 'linear-gradient(90deg, rgba(255,221,51,0) 0%, rgba(255,221,51,0.05) 30%, rgba(255,221,51,0.12) 60%, rgba(255,221,51,0.25) 100%)',
    text: '#996600',
    glow: 'rgba(255,221,51,0.15)'
  },
  green: {
    gradient: 'linear-gradient(90deg, rgba(102,255,102,0) 0%, rgba(102,255,102,0.05) 30%, rgba(102,255,102,0.12) 60%, rgba(102,255,102,0.25) 100%)',
    text: '#006600',
    glow: 'rgba(102,255,102,0.15)'
  },
  purple: {
    gradient: 'linear-gradient(90deg, rgba(179,102,255,0) 0%, rgba(179,102,255,0.05) 30%, rgba(179,102,255,0.12) 60%, rgba(179,102,255,0.25) 100%)',
    text: '#6600cc',
    glow: 'rgba(179,102,255,0.15)'
  },
};

// @@@ Main App Component
export default function App() {
  const isMobile = useMobile();
  const { isAuthenticated, isLoading } = useAuth();
  const { t, i18n } = useTranslation();
  const mobileNavHeight = 64;
  const mobileBottomOffset = isMobile
    ? `calc(${mobileNavHeight}px + env(safe-area-inset-bottom, 0px))`
    : '0px';
  const mobileTopInset = isMobile ? 'env(safe-area-inset-top, 0px)' : '48px';
  const viewTopOffset = isMobile ? 0 : 48;
  const writingBottomPadding = isMobile
    ? `calc(${mobileNavHeight}px + env(safe-area-inset-bottom, 0px) + 12px)`
    : '41px';

  // @@@ Auth screen state
  const [authScreen, setAuthScreen] = useState<'login' | 'register'>('login');
  const [showMigrationDialog, setShowMigrationDialog] = useState(false);
  const [isMigrating, setIsMigrating] = useState(false);
  const currentLanguage = (i18n.language || 'en').split('-')[0];
  const [showEnergyBar, setShowEnergyBar] = useState(() => {
    const stored = localStorage.getItem('show-energy-bar');
    return stored ? stored === 'true' : true;
  });

  useEffect(() => {
    localStorage.setItem('show-energy-bar', String(showEnergyBar));
  }, [showEnergyBar]);
  const handleUILanguageChange = useCallback((code: string) => {
    if (code !== currentLanguage) {
      i18n.changeLanguage(code);
    }
  }, [currentLanguage, i18n]);

  const [currentView, setCurrentView] = useState<'writing' | 'settings' | 'timeline' | 'analysis' | 'decks'>('writing');
  const [showCalendarPopup, setShowCalendarPopup] = useState(false);
  const [voiceConfigs, setVoiceConfigs] = useState<Record<string, VoiceConfig>>({});

  const browserTimezone = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
      return 'UTC';
    }
  }, []);
  const [stateConfig, setStateConfig] = useState(() => getStateConfig());

  const {
    engineRef,
    state,
    setState,
    selectedState,
    setSelectedState,
    selectedStateLoading,
    userTimezone,
    ensureStateForPersistence,
    getFirstLineFromState,
    saveSessionToDatabase,
    startDetachedBlankSession,
    handleNewSession,
    confirmStartFresh
  } = useSessionLifecycle({
    isAuthenticated,
    browserTimezone,
    setVoiceConfigs,
    setStateConfig
  });

  // @@@ Chat widget state
  const [dropdownVisible, setDropdownVisible] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ x: 0, y: 0 });
  const [dropdownTriggerCellId, setDropdownTriggerCellId] = useState<string | null>(null);
  const [chatProcessing, setChatProcessing] = useState<Set<string>>(new Set());

  // @@@ Warning dialog state
  const [showWarning, setShowWarning] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);  // @@@ Track scroll container for position preservation
  const savedScrollTop = useRef<number>(0);  // @@@ Save scroll position across re-renders

  // @@@ Comment alignment state
  const [commentsAligned, setCommentsAligned] = useState(false);

  // @@@ Writing inspiration/suggestion state
  const {
    currentInspiration,
    isDisappearing: inspirationDisappearing,
    isAppearing: inspirationAppearing,
    onTextChange: onInspirationTextChange,
    setTextGetter: setInspirationTextGetter,
  } = useInspiration();

  // @@@ Provide text getter to inspiration hook for validation
  useEffect(() => {
    setInspirationTextGetter(() => {
      if (!engineRef.current) return '';
      const cells = engineRef.current.getState().cells;
      return cells
        .filter(c => c.type === 'text')
        .map(c => (c as TextCell).content)
        .join('');
    });
  }, [setInspirationTextGetter]);

  // @@@ Text cell management (IME, refs, dropdown helpers)
  const {
    localTexts,
    composingCells,
    textareaRefs,
    refsReady,
    setRefsReady,
    handleTextChange,
    handleCompositionStart,
    handleCompositionEnd,
    handlePaste,
    handleKeyDown: handleTextCellKeyDown,
    createTextareaRef,
  } = useTextCells({
    engineRef,
    state,
    onInspirationTextChange,
    selectedState,
    dropdownVisible,
    dropdownTriggerCellId,
    onDropdownClose: () => {
      setDropdownVisible(false);
      setDropdownTriggerCellId(null);
    }
  });

  const { userTalking, handleToggleTalking } = useVoiceInput({
    engineRef,
    textareaRefs,
    isAuthenticated,
  });

  // @@@ Comment management (grouping, navigation, chat)
  const {
    commentGroups,
    groupPages,
    handleGroupNavigate,
    expandedCommentId,
    setExpandedCommentId,
    mobileActiveComment,
    handleCursorChange,
    handleCommentStar,
    handleCommentKill,
    handleCommentChatSend,
    commentChatProcessing,
  } = useComments({
    state,
    textareaRefs,
    refsReady,
    selectedState,
    stateConfig,
    isMobile,
    engineRef,
  });

  const energyThreshold = 50;
  const appliedComments = state?.commentors.filter(c => c.appliedAt) ?? [];
  const lastEntry = state?.weightPath[state.weightPath.length - 1];
  const currentEnergy = lastEntry?.energy || 0;
  const usedEnergy = appliedComments.length * energyThreshold;
  const unusedEnergy = currentEnergy - usedEnergy;
  const safeUnusedEnergy = Math.max(unusedEnergy, 0);
  const energyLevel = Math.floor(safeUnusedEnergy / energyThreshold);
  const energyRemainder = safeUnusedEnergy % energyThreshold;
  const [energyPulseKey, setEnergyPulseKey] = useState(0);
  const energyLevelRef = useRef(0);
  const [showFullEnergy, setShowFullEnergy] = useState(false);
  const fullEnergyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const energyProgress = showFullEnergy ? 1 : energyRemainder / energyThreshold;
  const mobileNavItems = [
    { key: 'writing' as const, label: t('nav.writing'), icon: FaPenNib },
    { key: 'timeline' as const, label: t('nav.timeline'), icon: FaRegClock },
    { key: 'analysis' as const, label: t('nav.analysis'), icon: FaChartBar },
    { key: 'decks' as const, label: t('nav.decks'), icon: FaLayerGroup },
    { key: 'settings' as const, label: t('nav.settings'), icon: FaCog },
  ];

  useEffect(() => {
    const prevLevel = energyLevelRef.current;
    if (energyLevel > prevLevel) {
      setEnergyPulseKey((key) => key + 1);
      setShowFullEnergy(true);
      if (fullEnergyTimeoutRef.current) {
        clearTimeout(fullEnergyTimeoutRef.current);
      }
      fullEnergyTimeoutRef.current = setTimeout(() => {
        setShowFullEnergy(false);
      }, 200);
    }
    energyLevelRef.current = energyLevel;
  }, [energyLevel]);

  useEffect(() => {
    return () => {
      if (fullEnergyTimeoutRef.current) {
        clearTimeout(fullEnergyTimeoutRef.current);
      }
    };
  }, []);

  // @@@ CRITICAL: Resize textareas then restore scroll position
  // Order matters: resize first (changes content height), then restore scroll
  // Triggers: on mount (refsReady) and when cells added/deleted (cells.length)
  useLayoutEffect(() => {
    // 1. Resize textareas first (if refs are ready)
    if (refsReady > 0) {
      textareaRefs.current.forEach((textarea) => {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
      });
    }

    // 2. Then restore scroll position (after heights are correct)
    if (scrollContainerRef.current && savedScrollTop.current > 0) {
      scrollContainerRef.current.scrollTop = savedScrollTop.current;
    }
  }, [refsReady, state?.cells.length]);

  // @@@ Trigger re-render when returning to writing view to recalculate comment positions
  useEffect(() => {
    if (currentView === 'writing') {
      // Force re-render to recalculate comment positions
      setRefsReady(prev => prev + 1);
    }
  }, [currentView]);

  // @@@ Force recalculation when selectedState changes (StateChooser height changes)
  useEffect(() => {
    if (selectedState) {
      // Small delay to ensure StateChooser has collapsed and DOM has settled
      const timer = setTimeout(() => {
        setRefsReady(prev => prev + 1);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [selectedState]);


  // @@@ Fetch default voices from backend and load from deck system
  useEffect(() => {
    getDefaultVoices().then(async backendVoices => {
      const converted: Record<string, VoiceConfig> = {};
      for (const [name, data] of Object.entries(backendVoices)) {
        const v = data as any;
        converted[name] = {
          name,
          systemPrompt: v.systemPrompt,  // @@@ Fixed: was v.tagline (wrong field name)
          enabled: true,
          icon: v.icon,
          color: v.color
        };
      }

      // @@@ Try loading from deck system first, then localStorage, then defaults
      const deckVoices = await loadVoicesFromDecks();
      const hasDecks = Object.keys(deckVoices).length > 0;
      const configs = hasDecks ? deckVoices : (getVoices() || converted);
      setVoiceConfigs(configs);

      console.log(`📚 Loaded voices from: ${hasDecks ? 'deck system' : 'localStorage or defaults'}`);

      // Update engine with voice configs
      if (engineRef.current) {
        engineRef.current.setVoiceConfigs(configs);
      }
    });
  }, []);

  // @@@ Update engine when voice configs change
  useEffect(() => {
    if (engineRef.current && Object.keys(voiceConfigs).length > 0) {
      engineRef.current.setVoiceConfigs(voiceConfigs);
    }
  }, [voiceConfigs]);

  // @@@ Reload state config when returning to writing view
  useEffect(() => {
    if (currentView === 'writing') {
      setStateConfig(getStateConfig());
    }
  }, [currentView]);

  // @@@ Check for localStorage migration after login
  useEffect(() => {
    const checkMigration = async () => {
      if (!isAuthenticated || isLoading) return;

      try {
        // Get user preferences from database (includes first_login_completed)
        const { getPreferences } = await import('./api/voiceApi');
        const preferences = await getPreferences();

        // If user has already completed first login, clear localStorage
        if (preferences?.first_login_completed) {
          // Clear all app data from localStorage (keep only auth token)
          Object.values(STORAGE_KEYS).forEach(key => {
            if (key !== STORAGE_KEYS.AUTH_TOKEN) {
              localStorage.removeItem(key);
            }
          });
          return;
        }

        // First time login - check for localStorage data to migrate
        const hasLocalData =
          localStorage.getItem(STORAGE_KEYS.EDITOR_STATE) ||
          localStorage.getItem(STORAGE_KEYS.CALENDAR_ENTRIES) ||
          localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES) ||
          localStorage.getItem(STORAGE_KEYS.VOICE_CONFIGS) ||
          localStorage.getItem(STORAGE_KEYS.META_PROMPT) ||
          localStorage.getItem(STORAGE_KEYS.STATE_CONFIG) ||
          localStorage.getItem(STORAGE_KEYS.SELECTED_STATE) ||
          localStorage.getItem(STORAGE_KEYS.ANALYSIS_REPORTS);

        if (hasLocalData) {
          console.log('🔍 First login with localStorage data, showing migration dialog');
          setShowMigrationDialog(true);
        } else {
          // No localStorage data, just mark first login as completed
          console.log('🔍 First login without localStorage data, marking as completed');
          const { markFirstLoginCompleted } = await import('./api/voiceApi');
          await markFirstLoginCompleted();
        }
      } catch (error) {
        console.error('Failed to check migration status:', error);
      }
    };

    checkMigration();
  }, [isAuthenticated, isLoading]);

  // @@@ Keep focus on the lone blank text cell (after resets / clears)
  useEffect(() => {
    if (!state) return;

    const textCells = state.cells.filter(c => c.type === 'text') as TextCell[];
    if (textCells.length !== 1) return;

    const firstCell = textCells[0];
    if (firstCell.content.trim().length > 0) return;

    const focusEditor = () => {
      const textarea = textareaRefs.current.get(firstCell.id);
      if (textarea && document.activeElement !== textarea) {
        textarea.focus();
        textarea.selectionStart = 0;
        textarea.selectionEnd = 0;
      }
    };

    const textarea = textareaRefs.current.get(firstCell.id);
    if (textarea) {
      focusEditor();
      return;
    }

    const timer = window.setTimeout(focusEditor, 0);
    return () => window.clearTimeout(timer);
  }, [state, refsReady]);

  const handleConfirmStartFresh = useCallback(() => {
    setShowWarning(false);
    confirmStartFresh();
  }, [confirmStartFresh]);

  const handleNewSessionClick = useCallback(() => {
    handleNewSession(state);
  }, [handleNewSession, state]);

  const handleSaveToday = useCallback(async () => {
    if (!engineRef.current) return;
    if (!isAuthenticated) {
      const toast = document.createElement('div');
      toast.textContent = 'Please sign in to save';
      toast.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: #f44336;
        color: white;
        padding: 12px 20px;
        borderRadius: 6px;
        fontSize: 14px;
        fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        zIndex: 10000;
        boxShadow: 0 4px 12px rgba(0,0,0,0.15);
      `;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => document.body.removeChild(toast), 300);
      }, 2000);
      return;
    }
    const currentState = ensureStateForPersistence();
    if (!currentState) return;

    try {
      const firstLine = getFirstLineFromState(currentState);
      const savedSessionId = await saveSessionToDatabase(currentState, firstLine);
      engineRef.current.setCurrentEntryId(savedSessionId);

      const toast = document.createElement('div');
      toast.textContent = 'Saved';
      toast.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: #4CAF50;
        color: white;
        padding: 12px 20px;
        borderRadius: 6px;
        fontSize: 14px;
        fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        zIndex: 10000;
        boxShadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => document.body.removeChild(toast), 300);
      }, 2000);
    } catch (error) {
      console.error('Failed to save:', error);
      // Show error toast
      const toast = document.createElement('div');
      toast.textContent = 'Save failed';
      toast.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: #f44336;
        color: white;
        padding: 12px 20px;
        borderRadius: 6px;
        fontSize: 14px;
        fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        zIndex: 10000;
        boxShadow: 0 4px 12px rgba(0,0,0,0.15);
      `;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => document.body.removeChild(toast), 300);
      }, 2000);
    }
  }, [ensureStateForPersistence, getFirstLineFromState, isAuthenticated, saveSessionToDatabase]);

  const handleLoadEntry = useCallback((entry: CalendarEntry) => {
    if (!engineRef.current) return;

    const nextState: EditorState = {
      ...entry.state,
      id: entry.id,
      createdAt: entry.state.createdAt ?? new Date().toISOString()
    };

    engineRef.current.loadState(nextState);
    if (nextState.selectedState !== undefined) {
      setSelectedState(nextState.selectedState);
    }

    setRefsReady(prev => prev + 1);
    setShowCalendarPopup(false);
  }, []);

  const handleCalendarEntryDeleted = useCallback((entryId: string) => {
    if (!entryId || !engineRef.current) return;
    const currentId = engineRef.current.getState().id;
    if (currentId === entryId) {
      startDetachedBlankSession();
    }
  }, [startDetachedBlankSession]);

    const handleStateChoose = useCallback(async (stateId: string) => {
      const todayKey = getTodayKeyInTimezone(userTimezone);

      if (engineRef.current) {
        const currentState = engineRef.current.getState();
        const sessionDate = currentState.createdAt
          ? getLocalDayKey(currentState.createdAt, userTimezone)
          : null;

        if (sessionDate && sessionDate !== todayKey) {
          console.log(`📅 State chosen for old session (${sessionDate}). Starting fresh for ${todayKey}.`);
          await startDetachedBlankSession(true);
        }

        const stateToUpdate = engineRef.current.getState();
        stateToUpdate.selectedState = stateId;
        if (!stateToUpdate.createdAt) {
          stateToUpdate.createdAt = new Date().toISOString();
        }
        setState(stateToUpdate);
      }

      setSelectedState(stateId);

      // @@@ KEEP: Also save to global preferences for daily reset check
      if (isAuthenticated) {
        try {
          const { savePreferences } = await import('./api/voiceApi');
          await savePreferences({ selected_state: stateId });
          // Database updated_at will be used for daily reset check
        } catch (error) {
          console.error('Failed to save state to database:', error);
        }
      } else {
        localStorage.setItem(STORAGE_KEYS.SELECTED_STATE, stateId);
        localStorage.setItem('selected-state-date', todayKey);
      }
    }, [isAuthenticated, startDetachedBlankSession, userTimezone]);

  // @@@ Insert @ character at the end of last text cell
  const handleInsertAgent = useCallback(() => {
    if (!state || !engineRef.current) return;

    // Find last text cell
    const lastTextCell = [...state.cells].reverse().find(c => c.type === 'text');
    if (!lastTextCell) return;

    const textarea = textareaRefs.current.get(lastTextCell.id);
    if (!textarea) return;

    // Insert @ character at the end
    const currentContent = (lastTextCell as TextCell).content;
    const newContent = currentContent + '@';

    // Update the text
    engineRef.current.updateTextCell(lastTextCell.id, newContent);

    // Focus the textarea and position cursor after @
    setTimeout(() => {
      textarea.focus();
      textarea.selectionStart = newContent.length;
      textarea.selectionEnd = newContent.length;

      // Show dropdown
      const rect = textarea.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(textarea);
      const lineHeight = parseFloat(computedStyle.lineHeight) || 32;
      const linesBefore = newContent.substring(0, newContent.length).split('\n').length - 1;

      setDropdownPosition({
        x: rect.left + 10,
        y: rect.top + (linesBefore * lineHeight) + lineHeight + 5
      });
      setDropdownTriggerCellId(lastTextCell.id);
      setDropdownVisible(true);
    }, 0);
  }, [state]);

  // @@@ Toggle comment alignment
  const handleToggleAlign = useCallback(() => {
    setCommentsAligned(prev => !prev);
  }, []);

  // @@@ Handle localStorage migration
  const handleMigrateData = useCallback(async () => {
    setIsMigrating(true);
    try {
      // Export all localStorage data (convert null to undefined)
      const migrationData = {
        currentSession: localStorage.getItem(STORAGE_KEYS.EDITOR_STATE) ?? undefined,
        calendarEntries: localStorage.getItem(STORAGE_KEYS.CALENDAR_ENTRIES) ?? undefined,
        dailyPictures: localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES) ?? undefined,
        voiceCustomizations: localStorage.getItem(STORAGE_KEYS.VOICE_CONFIGS) ?? undefined,
        metaPrompt: localStorage.getItem(STORAGE_KEYS.META_PROMPT) ?? undefined,
        stateConfig: localStorage.getItem(STORAGE_KEYS.STATE_CONFIG) ?? undefined,
        selectedState: localStorage.getItem(STORAGE_KEYS.SELECTED_STATE) ?? undefined,
        analysisReports: localStorage.getItem(STORAGE_KEYS.ANALYSIS_REPORTS) ?? undefined,
        oldDocument: localStorage.getItem('document') ?? undefined
      };

      // Log what we're about to send
      console.log('📦 Migration data being sent:');
      console.log('  - currentSession:', migrationData.currentSession ? `${migrationData.currentSession.length} chars` : 'null');
      console.log('  - calendarEntries:', migrationData.calendarEntries ? `${migrationData.calendarEntries.length} chars` : 'null');
      console.log('  - dailyPictures:', migrationData.dailyPictures ? `${migrationData.dailyPictures.length} chars` : 'null');

      // Call backend migration endpoint
      const result = await importLocalData(migrationData);

      // Mark first login as completed in database
      const { markFirstLoginCompleted } = await import('./api/voiceApi');
      await markFirstLoginCompleted();

      // Clear ALL localStorage data (keep only auth token)
      Object.values(STORAGE_KEYS).forEach(key => {
        if (key !== STORAGE_KEYS.AUTH_TOKEN) {
          localStorage.removeItem(key);
        }
      });

      setShowMigrationDialog(false);

      // Show success message
      alert(`Migration successful! Imported:\n- ${result.imported.sessions} sessions\n- ${result.imported.pictures} pictures\n- ${result.imported.preferences} preferences\n- ${result.imported.reports} reports`);
    } catch (error: any) {
      console.error('Migration failed:', error);

      // Provide helpful error message based on error type
      let errorMsg = 'Migration failed: ';
      if (error.message?.includes('413') || error.message?.includes('too large')) {
        errorMsg += 'Your data is too large to migrate in one request.\n\n';
        errorMsg += 'This is a known issue that will be fixed soon.\n';
        errorMsg += 'For now, you can:\n';
        errorMsg += '1. Skip migration and start fresh, or\n';
        errorMsg += '2. Wait for the fix and try again later';
      } else {
        errorMsg += error.message + '\n\nYou can try again later from Settings.';
      }

      alert(errorMsg);
    } finally {
      setIsMigrating(false);
    }
  }, []);

  const handleSkipMigration = useCallback(async () => {
    try {
      // Mark first login as completed in database
      const { markFirstLoginCompleted } = await import('./api/voiceApi');
      await markFirstLoginCompleted();

      // Clear ALL localStorage data (keep only auth token)
      Object.values(STORAGE_KEYS).forEach(key => {
        if (key !== STORAGE_KEYS.AUTH_TOKEN) {
          localStorage.removeItem(key);
        }
      });

      setShowMigrationDialog(false);
    } catch (error) {
      console.error('Failed to skip migration:', error);
      alert('Failed to skip migration. Please try again.');
    }
  }, []);

  const handleAuthSuccess = useCallback(() => {
    // After successful login/register, check for migration
    // This is handled by the useEffect hook above
  }, []);

  // @@@ Handle @ key press for agent dropdown
  const handleKeyDown = useCallback((cellId: string, e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    handleTextCellKeyDown(cellId, e);

    if (e.key === '@' && !composingCells.has(cellId)) {
      const textarea = e.currentTarget;
      setTimeout(() => {
        if (textarea) {
          const cursorPos = textarea.selectionStart;
          const textBeforeCursor = textarea.value.substring(0, cursorPos);
          const lines = textBeforeCursor.split('\n');
          const linesBefore = lines.length - 1;
          const currentLineText = lines[lines.length - 1];

          const computedStyle = window.getComputedStyle(textarea);
          const lineHeight = parseFloat(computedStyle.lineHeight) || 32;
          const fontSize = parseFloat(computedStyle.fontSize) || 18;
          const rect = textarea.getBoundingClientRect();
          const padding = parseFloat(computedStyle.paddingLeft) || 0;

          const charWidth = fontSize * 0.6;
          const horizontalOffset = padding + (currentLineText.length * charWidth);

          setDropdownPosition({
            x: rect.left + horizontalOffset,
            y: rect.top + (linesBefore * lineHeight) + lineHeight + 5
          });
          setDropdownTriggerCellId(cellId);
          setDropdownVisible(true);
        }
      }, 0);
    }
  }, [composingCells, handleTextCellKeyDown]);

  // @@@ Handle agent selection from dropdown
  const handleAgentSelect = useCallback((voiceName: string, voiceConfig: VoiceConfig) => {
    setDropdownVisible(false);

    if (!engineRef.current || !dropdownTriggerCellId) return;

    const textarea = textareaRefs.current.get(dropdownTriggerCellId);
    if (!textarea) {
      setDropdownTriggerCellId(null);
      return;
    }

    const cursorPos = textarea.selectionStart;

    // Create chat widget
    const chatWidget = new ChatWidget(voiceName, voiceConfig);

    // Insert widget at cursor (engine will handle @ removal)
    engineRef.current.insertWidgetAtCursor(dropdownTriggerCellId, cursorPos, 'chat', chatWidget.getData());
    setDropdownTriggerCellId(null);
  }, [dropdownTriggerCellId]);

  // @@@ Handle sending chat message
  const handleChatSend = useCallback(async (widgetId: string, message: string) => {
    if (!engineRef.current || !state) return;

    // Find widget
    const widgetCell = state.cells.find(c => c.type === 'widget' && c.id === widgetId);
    if (!widgetCell || widgetCell.type !== 'widget') return;

    const widgetData = widgetCell.data as ChatWidgetData;
    const chatWidget = ChatWidget.fromData(widgetData);

    // Add user message optimistically
    chatWidget.addUserMessage(message);
    engineRef.current.updateWidgetData(widgetId, chatWidget.getData());

    // Mark as processing
    setChatProcessing(prev => new Set(prev).add(widgetId));

    try {
      // Get ALL text from all text cells as unified context
      const allText = state.cells
        .filter(c => c.type === 'text')
        .map(c => (c as TextCell).content)
        .join('');

      const metaPrompt = getMetaPrompt();
      const statePrompt = selectedState && stateConfig.states[selectedState]
        ? stateConfig.states[selectedState].prompt
        : '';

      // @@@ Use voiceName (which is the voice ID/key) for backend lookup
      // Backend loads voice config from database using user_id from JWT
      const response = await chatWithVoice(
        widgetData.voiceName,  // This is the voice ID (key like "holder", "mirror")
        chatWidget.getConversationHistory().slice(0, -1), // Exclude last message (just added)
        message,
        allText,
        metaPrompt,
        statePrompt
      );

      // Add assistant response
      chatWidget.addAssistantMessage(response);
      engineRef.current.updateWidgetData(widgetId, chatWidget.getData());
    } catch (error) {
      console.error('Chat failed:', error);
      chatWidget.addAssistantMessage('Sorry, I encountered an error.');
      engineRef.current.updateWidgetData(widgetId, chatWidget.getData());
    } finally {
      setChatProcessing(prev => {
        const next = new Set(prev);
        next.delete(widgetId);
        return next;
      });
    }
  }, [state, selectedState, stateConfig]);

  // @@@ Handle deleting chat widget
  const handleChatDelete = useCallback((widgetId: string) => {
    if (!engineRef.current) return;
    engineRef.current.deleteCell(widgetId);
  }, []);

  // @@@ Helper to get watercolor background
  const getWatercolorBg = (color: string) => {
    const brushes: Record<string, string> = {
      yellow: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-9&color=ffff43)',
      blue: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-7&color=a3d5ff)',
      pink: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-8&color=ffb3d9)',
      green: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-6&color=b3ffb3)',
      purple: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-5&color=ddb3ff)'
    };
    return brushes[color] || 'none';
  };

  // @@@ Render highlighted text for a specific text content
  const renderHighlightedText = (text: string) => {
    if (!state) return null;

    const appliedComments = state.commentors.filter(c => c.appliedAt);

    if (appliedComments.length === 0) {
      return <div style={{ whiteSpace: 'pre-wrap' }}>{text}</div>;
    }

    // Find highlights in this specific text
    const highlights: Array<{ start: number; end: number; comment: Commentor }> = [];
    appliedComments.forEach(comment => {
      const index = findNormalizedPhrase(text, comment.phrase);
      if (index !== -1) {
        highlights.push({
          start: index,
          end: index + comment.phrase.length,
          comment
        });
      }
    });

    highlights.sort((a, b) => a.start - b.start);

    const elements: React.ReactNode[] = [];
    let lastEnd = 0;

    highlights.forEach((highlight, idx) => {
      if (highlight.start > lastEnd) {
        elements.push(
          <span key={`text-${idx}`}>
            {text.substring(lastEnd, highlight.start)}
          </span>
        );
      }

      elements.push(
        <span
          key={`highlight-${idx}`}
          className="voice-highlight"
          data-comment-id={highlight.comment.id}
          style={{
            margin: '-2px -6px',
            padding: '2px 6px',
            background: getWatercolorBg(highlight.comment.color),
            transition: 'all 0.2s ease'
          }}
        >
          {text.substring(highlight.start, highlight.end)}
        </span>
      );

      lastEnd = highlight.end;
    });

    if (lastEnd < text.length) {
      elements.push(
        <span key="text-final">
          {text.substring(lastEnd)}
        </span>
      );
    }

    return <div style={{ whiteSpace: 'pre-wrap' }}>{elements}</div>;
  };

  // @@@ Show loading state while checking auth
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
        fontSize: '18px',
        color: '#666'
      }}>
        Loading...
      </div>
    );
  }

  // @@@ Show auth screen if not authenticated
  const loginBannerUrl = `${import.meta.env.BASE_URL}login-banner.jpg`;

  if (!isAuthenticated) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: `linear-gradient(135deg, rgba(245,240,232,0.8) 0%, rgba(232,220,200,0.9) 100%), url(${loginBannerUrl})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        padding: '20px'
      }}>
        {authScreen === 'login' ? (
          <LoginForm
            onSuccess={handleAuthSuccess}
            onSwitchToRegister={() => setAuthScreen('register')}
          />
        ) : (
          <RegisterForm
            onSuccess={handleAuthSuccess}
            onSwitchToLogin={() => setAuthScreen('login')}
          />
        )}
      </div>
    );
  }

  if (!state || !engineRef.current) {
    return <div>Loading...</div>;
  }


  return (
    <>
      {/* @@@ Migration dialog */}
      {showMigrationDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10000,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: '#fffef9',
            border: '2px solid #d0c4b0',
            borderRadius: '12px',
            padding: '32px',
            maxWidth: '500px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}>
            <h2 style={{
              margin: '0 0 16px 0',
              fontSize: '24px',
              color: '#333',
              fontWeight: 600
            }}>
              Migrate Your Data?
            </h2>
            <p style={{
              margin: '0 0 24px 0',
              fontSize: '16px',
              lineHeight: '1.6',
              color: '#555'
            }}>
              We found data in your browser. Would you like to migrate it to your account?
              This will move all your sessions, pictures, and preferences to the cloud.
            </p>
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={handleMigrateData}
                disabled={isMigrating}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  border: 'none',
                  background: isMigrating ? '#ccc' : '#4a90e2',
                  borderRadius: '6px',
                  cursor: isMigrating ? 'not-allowed' : 'pointer',
                  fontSize: '16px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: '#fff',
                  fontWeight: 600,
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = '#357abd';
                }}
                onMouseLeave={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = '#4a90e2';
                }}
              >
                {isMigrating ? 'Migrating...' : 'Migrate Data'}
              </button>
              <button
                onClick={handleSkipMigration}
                disabled={isMigrating}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: '6px',
                  cursor: isMigrating ? 'not-allowed' : 'pointer',
                  fontSize: '16px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: '#666',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = '#fff';
                }}
              >
                Skip
              </button>
            </div>
          </div>
        </div>
      )}

      {/* @@@ Hide top nav on mobile */}
      {!isMobile && <TopNavBar currentView={currentView} onViewChange={setCurrentView} />}

      {currentView === 'writing' && (
        <div style={{
          display: 'flex',
          height: '100vh',
          paddingTop: mobileTopInset,
          paddingBottom: writingBottomPadding,  // @@@ Space for fixed stats bar + mobile nav
          fontFamily: 'system-ui, -apple-system, sans-serif',
          boxSizing: 'border-box'
        }}>
          {/* New Session "+" button - top left (desktop only) */}
          {!isMobile && (
            <button
              onClick={handleNewSessionClick}
              title="New Session"
              style={{
                position: 'fixed',
                left: '20px',
                top: '72px',
                zIndex: 101,
                width: '32px',
                height: '32px',
                border: 'none',
                borderRadius: '50%',
                backgroundColor: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                fontSize: '20px',
                fontWeight: '300',
                color: '#666',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f8f8f8';
                e.currentTarget.style.transform = 'scale(1.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#fff';
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              +
            </button>
          )}

          {/* Left toolbar - floating on top (desktop only) */}
          {!isMobile && (
            <div style={{
              position: 'fixed',
              left: '12px',
              top: '100px',
              zIndex: 100
            }}>
              <LeftToolbar
                onInsertAgent={handleInsertAgent}
                onToggleAlign={handleToggleAlign}
                onShowCalendar={() => setShowCalendarPopup(true)}
                onSaveToday={handleSaveToday}
                onToggleTalking={handleToggleTalking}
                isAligned={commentsAligned}
                isTalking={userTalking}
              />
            </div>
          )}

          {/* @@@ Mobile floating toolbar - top right corner */}
          {isMobile && (
            <div style={{
              position: 'fixed',
              top: 'calc(10px + env(safe-area-inset-top, 0px))',
              right: '10px',
              display: 'flex',
              gap: '8px',
              zIndex: 1000
            }}>
              <button
                onClick={handleNewSessionClick}
                title="New Session"
                style={{
                  width: '44px',
                  height: '44px',
                  border: 'none',
                  borderRadius: '50%',
                  backgroundColor: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                  fontSize: '24px',
                  fontWeight: '300',
                  color: '#666',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f8f8f8';
                  e.currentTarget.style.transform = 'scale(1.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#fff';
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                +
              </button>
              <button
                onClick={handleInsertAgent}
                title="Insert Agent Chat"
                style={{
                  width: '44px',
                  height: '44px',
                  border: 'none',
                  borderRadius: '50%',
                  backgroundColor: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  transition: 'all 0.2s ease',
                  fontSize: '24px',
                  fontWeight: 600,
                  color: '#333',
                  fontFamily: 'monospace'
                }}
              >
                @
              </button>
            </div>
          )}

          <div
            style={{
              flex: 1,
              position: 'relative',
              overflow: 'hidden',
              // @@@ Disable horizontal scrolling on mobile
              ...(isMobile ? { overflowX: 'hidden', touchAction: 'pan-y' } : {})
            }}
          >
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              width: '100%',
              margin: '0 auto'
            }}>
              <div
                ref={scrollContainerRef}  // @@@ Track scroll container for position preservation
                className="notebook-lines"
                onScroll={(e) => {
                  // @@@ Save scroll position whenever user scrolls manually
                  const target = e.currentTarget;
                  savedScrollTop.current = target.scrollTop;
                }}
                style={{
                  flex: 1,
                  position: 'relative',
                  overflow: 'auto',
                  padding: '20px',
                  paddingLeft: isMobile ? '20px' : '80px',  // @@@ Extra left padding for floating toolbar
                  paddingBottom: isMobile
                    ? `calc(80px + ${mobileNavHeight}px + env(safe-area-inset-bottom, 0px))`
                    : '80px',  // Extra space for smooth scrolling to bottom
                  backgroundColor: '#fffef9'  // @@@ Cream paper background for notebook lines
                }}>
                <div style={{
                  position: 'relative',
                  maxWidth: '600px'
                }}>
                  {/* State chooser widget - always shown, collapses when state selected */}
                  <div style={{
                    height: '32px',  // @@@ Fixed height to match one line interval
                    marginBottom: '10.8px'  // @@@ 1/3 line interval (32.4px / 3)
                  }}>
                    <StateChooser
                      stateConfig={stateConfig}
                      selectedState={state?.selectedState ?? selectedState}
                      selectedStateLoading={selectedStateLoading}
                      createdAt={state?.createdAt}
                      onChoose={handleStateChoose}
                    />
                  </div>

                  {/* Render cells sequentially with per-cell highlights */}
                  {state.cells.map((cell, idx) => {
                    if (cell.type === 'text') {
                      const textCell = cell as TextCell;
                      // Use local text if available, otherwise use engine state
                      const content = localTexts.get(cell.id) ?? textCell.content;

                      return (
                        <div key={cell.id} style={{
                          position: 'relative',
                          marginTop: idx === 0 ? '0.4px' : 0  // @@@ Align first line with 2nd notebook line
                        }}>
                          {/* Highlight layer for this cell */}
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            pointerEvents: 'none',
                            fontSize: '18px',
                            lineHeight: '1.8',
                            color: 'transparent',
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                            zIndex: 0
                          }}>
                            {renderHighlightedText(content)}
                          </div>

                          {/* Textarea for this cell */}
                          <textarea
                            ref={createTextareaRef(cell.id)}
                            value={content}
                            onChange={(e) => handleTextChange(cell.id, e.target.value)}
                            onCompositionStart={() => handleCompositionStart(cell.id)}
                            onCompositionEnd={(e) => handleCompositionEnd(cell.id, e)}
                            onPaste={(e) => handlePaste(cell.id, e)}
                            onSelect={(e) => handleCursorChange(cell.id, e)}
                            onClick={(e) => handleCursorChange(cell.id, e)}
                            onKeyUp={(e) => handleCursorChange(cell.id, e)}
                            onKeyDown={(e) => handleKeyDown(cell.id, e)}
                            placeholder={idx === 0 ? "Start writing..." : "Continue writing..."}
                            style={{
                              width: '100%',
                              border: 'none',
                              outline: 'none',
                              resize: 'none',
                              fontSize: '18px',
                              lineHeight: '1.8',
                              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                              background: 'transparent',
                              color: '#333',
                              caretColor: '#333',
                              position: 'relative',
                              zIndex: 1,
                              marginBottom: '0px',
                              overflow: 'hidden',
                              overflowWrap: 'break-word',
                              wordWrap: 'break-word',
                              whiteSpace: 'pre-wrap',
                              minHeight: '32px',
                              height: 'auto'
                            }}
                          />

                        </div>
                      );
                    } else if (cell.type === 'widget' && cell.widgetType === 'chat') {
                      return (
                        <ChatWidgetUI
                          key={cell.id}
                          data={cell.data as ChatWidgetData}
                          onSendMessage={(msg) => handleChatSend(cell.id, msg)}
                          onDelete={() => handleChatDelete(cell.id)}
                          isProcessing={chatProcessing.has(cell.id)}
                        />
                      );
                    }
                    return null;
                  })}

                  {/* @@@ Inline Inspiration */}
                  <InspirationHint
                    inspiration={currentInspiration}
                    isDisappearing={inspirationDisappearing}
                    isAppearing={inspirationAppearing}
                  />
                </div>

                {/* Comments layer (absolute positioned) - hide on mobile */}
                {!isMobile && (() => {
                  // @@@ Calculate global max line width across all groups for alignment
                  const globalMaxLineWidth = Math.max(
                    0,
                    ...Array.from(commentGroups.values()).map(g => g.maxLineWidth)
                  );

                  return Array.from(commentGroups.entries()).map(([groupKey, group]) => {
                    const currentIndex = groupPages.get(groupKey) || 0;

                    // @@@ Get the specific textarea for this group's cell
                    const cellTextarea = textareaRefs.current.get(group.cellId);
                    if (!cellTextarea) return null;

                    // @@@ Use offsetTop relative to the content container (with maxWidth: 600px)
                    // This div is at line 1031 with position: relative
                    const cellWrapper = cellTextarea.parentElement; // The div with position: relative
                    if (!cellWrapper) return null;

                    const cellOffsetTop = cellWrapper.offsetTop;

                    // @@@ Calculate line height from textarea styles
                    const computedStyle = window.getComputedStyle(cellTextarea);
                    const fontSize = parseFloat(computedStyle.fontSize) || 18;
                    const lineHeightRatio = parseFloat(computedStyle.lineHeight) / fontSize || 1.8;
                    const lineHeight = fontSize * lineHeightRatio;

                    const containerPadding = parseFloat(window.getComputedStyle(cellWrapper.parentElement || cellWrapper).paddingLeft) || 20;
                    const gap = Math.max(30, window.innerWidth * 0.02);
                    // @@@ Use global max width when aligned, otherwise use group's max width
                    const lineWidthToUse = commentsAligned ? globalMaxLineWidth : group.maxLineWidth;
                    const leftPosition = containerPadding + lineWidthToUse + gap + (lineHeight * 2);  // @@@ Move right 2 line heights

                    // @@@ Position using offsetTop (scroll-independent)
                    // centerY is already relative to cell's top, so just add:
                    // - cellOffsetTop: position relative to content container
                    // - 20px: scroll container top padding
                    // - 32px: StateChooser fixed height
                    // - 10.8px: StateChooser marginBottom
                    // - subtract lineHeight * 2: move up to top of 2-line block
                    // - subtract lineHeight / 3: additional upward adjustment
                    const topPosition = cellOffsetTop + group.centerY + 20 + 32 + 10.8 - lineHeight * 2 - (lineHeight / 3);

                    // @@@ If expanded, use the expanded comment ID (stable), otherwise use current index
                    const isExpanded = group.comments.some(c => c.id === expandedCommentId);
                    const displayedComment = isExpanded
                      ? group.comments.find(c => c.id === expandedCommentId)!
                      : group.comments[currentIndex];
                    const displayedIndex = isExpanded
                      ? group.comments.findIndex(c => c.id === expandedCommentId)
                      : currentIndex;

                    if (!displayedComment) return null;

                    return (
                      <CommentGroupCard
                        key={groupKey}
                        comments={group.comments}
                        currentIndex={displayedIndex}
                        onNavigate={(idx) => handleGroupNavigate(groupKey, idx)}
                        position={{
                          top: topPosition,
                          left: leftPosition
                        }}
                        isExpanded={isExpanded}
                        onToggleExpand={() => {
                          setExpandedCommentId(prev => {
                            const anyExpanded = group.comments.some(c => c.id === prev);
                            if (anyExpanded) return null;
                            return displayedComment.id;
                          });
                        }}
                        onStar={() => handleCommentStar(displayedComment.id)}
                        onKill={() => handleCommentKill(displayedComment.id)}
                        onSendChatMessage={(msg) => handleCommentChatSend(displayedComment.id, msg)}
                        isChatProcessing={commentChatProcessing.has(displayedComment.id)}
                        voiceConfigs={voiceConfigs}
                      />
                    );
                  });
                })()}

                {/* @@@ Mobile comment popup - show when cursor is in highlighted area */}
                {isMobile && mobileActiveComment && (
                  <div style={{
                    position: 'fixed',
                    bottom: `calc(${mobileNavHeight}px + 20px + env(safe-area-inset-bottom, 0px))`,
                    left: '10px',
                    right: '10px',
                    background: '#fff',
                    border: '2px solid #ddd',
                    borderRadius: '12px',
                    padding: '16px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
                    zIndex: 100,
                    fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                    animation: 'slideInFromBottom 0.3s ease-out'
                  }}>
                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      alignItems: 'flex-start'
                    }}>
                      {(() => {
                        const Icon = iconMap[mobileActiveComment.icon as keyof typeof iconMap] || FaBrain;
                        const colors = colorMap[mobileActiveComment.color] || colorMap.blue;
                        return (
                          <>
                            <Icon size={20} color={colors.text} style={{ marginTop: '2px', flexShrink: 0 }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontWeight: 600, fontSize: '16px', color: colors.text, marginBottom: '8px' }}>
                                {mobileActiveComment.voice}
                              </div>
                              <div style={{ fontSize: '15px', lineHeight: '1.5', color: '#444' }}>
                                {mobileActiveComment.comment}
                              </div>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                )}
              </div>

              {/* Debug stats bar at bottom */}
              <div style={{
                position: 'fixed',
                bottom: isMobile ? mobileBottomOffset : 0,
                left: 0,
                right: 0,
                padding: isMobile ? '8px 12px' : '10px 20px',
                borderTop: '1px solid #e0e0e0',
                fontSize: isMobile ? '11px' : '12px',
                color: '#666',
                display: 'flex',
                gap: isMobile ? '12px' : '20px',
                flexWrap: isMobile ? 'wrap' : 'nowrap',
                backgroundColor: '#fafafa',
                zIndex: 50
              }}>
                <span>Weight: {lastEntry?.weight || 0}</span>
                <span>Applied: {appliedComments.length}</span>
                <span>Groups: {commentGroups.size}</span>
                {showEnergyBar && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>Energy:</span>
                    <span
                      key={energyPulseKey}
                      style={{
                        display: 'inline-flex',
                        padding: '2px',
                        borderRadius: '999px',
                        animation: energyPulseKey > 0 ? 'energyPulse 0.6s ease-out' : 'none'
                      }}
                    >
                      <span style={{
                        width: isMobile ? '84px' : '120px',
                        height: '8px',
                        borderRadius: '999px',
                        background: 'rgba(102, 102, 102, 0.2)',
                        overflow: 'hidden',
                        display: 'block'
                      }}>
                        <span
                          style={{
                            display: 'block',
                            height: '100%',
                            width: `${Math.round(energyProgress * 100)}%`,
                            background: '#666',
                            borderRadius: '999px',
                            transition: 'width 0.25s ease',
                          }}
                        />
                      </span>
                    </span>
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Agent dropdown */}
          {dropdownVisible && (
            <AgentDropdown
              voices={voiceConfigs}
              position={dropdownPosition}
              onSelect={handleAgentSelect}
              onClose={() => setDropdownVisible(false)}
            />
          )}
        </div>
      )}
      {currentView === 'decks' && (
        <div style={{
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          background: '#f8f0e6',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <DeckManager onUpdate={async () => {
            // @@@ Reload voice configs from deck system
            console.log('Deck system updated, reloading voices...');
            const updatedVoices = await loadVoicesFromDecks();
            setVoiceConfigs(updatedVoices);

            if (engineRef.current) {
              engineRef.current.setVoiceConfigs(updatedVoices);
            }

            console.log(`✅ Loaded ${Object.keys(updatedVoices).length} enabled voices`);
          }} />
        </div>
      )}
      {currentView === 'settings' && (
        <div style={{
          flex: 1,
          display: 'flex',
          justifyContent: 'center',
          padding: isMobile ? '24px 16px 120px 16px' : '60px 40px 120px 40px',
          overflow: 'auto',
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          background: '#f8f0e6'
        }}>
          <div style={{
            maxWidth: 800,
            width: '100%'
          }}>
            <section style={{ marginBottom: 48 }}>
              <h2 style={{
                fontSize: 24,
                fontWeight: 600,
                color: '#2c2c2c',
                marginBottom: 16,
                fontFamily: 'Georgia, "Times New Roman", serif'
              }}>
                {t('nav.settings')}
              </h2>
              <div style={{
                background: 'rgba(255, 255, 255, 0.5)',
                border: '1px solid #d0c4b0',
                borderRadius: 8,
                padding: 24
              }}>
                <div style={{ marginBottom: 12 }}>
                  <label style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: '#2c2c2c',
                    marginBottom: 6,
                    display: 'block',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                  }}>
                    Language / 语言
                  </label>
                  <p style={{
                    margin: 0,
                    fontSize: 13,
                    color: '#666',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                  }}>
                    {t('settings.language.description')}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {LANGUAGE_CODES.map(code => {
                    const isActive = currentLanguage === code;
                    return (
                      <button
                        key={code}
                        onClick={() => handleUILanguageChange(code)}
                        style={{
                          padding: '8px 16px',
                          background: isActive ? '#2c2c2c' : 'transparent',
                          color: isActive ? '#fff' : '#666',
                          border: isActive ? 'none' : '1px solid #d0c4b0',
                          borderRadius: 6,
                          fontSize: 14,
                          fontWeight: 500,
                          cursor: isActive ? 'default' : 'pointer',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          boxShadow: isActive ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        {t(`settings.language.options.${code}`)}
                      </button>
                    );
                  })}
                </div>

                <p style={{
                  marginTop: 12,
                  fontSize: 12,
                  color: '#8a7a69',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                }}>
                  {t('settings.language.preview')}
                </p>

                <div style={{
                  marginTop: 20,
                  paddingTop: 16,
                  borderTop: '1px dashed #d0c4b0'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12
                  }}>
                    <div>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: '#2c2c2c',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                      }}>
                        Energy Bar / 能量条
                      </div>
                      <div style={{
                        marginTop: 6,
                        fontSize: 12,
                        color: '#666',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                      }}>
                        Toggle the energy progress bar in the bottom stats line.
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowEnergyBar(prev => !prev)}
                      aria-pressed={showEnergyBar}
                      style={{
                        width: 44,
                        height: 24,
                        borderRadius: 999,
                        border: showEnergyBar ? '1px solid #2c2c2c' : '1px solid #d0c4b0',
                        background: showEnergyBar ? '#2c2c2c' : 'transparent',
                        cursor: 'pointer',
                        position: 'relative',
                        padding: 0,
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <span style={{
                        position: 'absolute',
                        top: 3,
                        left: showEnergyBar ? 'auto' : 4,
                        right: showEnergyBar ? 4 : 'auto',
                        width: 16,
                        height: 16,
                        borderRadius: '50%',
                        background: showEnergyBar ? '#fff' : '#8a7a69',
                        transition: 'all 0.2s ease'
                      }} />
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {/* About Content */}
            <AboutView />
          </div>
        </div>
      )}
      {/* @@@ Always render timeline to pre-load data and position scroll */}
      <div style={{
        position: 'fixed',
        top: viewTopOffset,
        left: 0,
        right: 0,
        bottom: mobileBottomOffset,
        background: '#f8f0e6',
        display: currentView === 'timeline' ? 'flex' : 'none',
        overflow: 'hidden'
      }}>
        <CollectionsView
          isVisible={currentView === 'timeline'}
          voiceConfigs={voiceConfigs}
          timezone={userTimezone}
        />
      </div>
      {currentView === 'analysis' && (
        <div style={{
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          background: '#f8f0e6',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <AnalysisView />
        </div>
      )}

      {isMobile && (
        <nav style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          height: `calc(${mobileNavHeight}px + env(safe-area-inset-bottom, 0px))`,
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          background: '#f8f0e6',
          borderTop: '1px solid #d0c4b0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-around',
          zIndex: 900
        }}>
          {mobileNavItems.map((item) => {
            const isActive = currentView === item.key;
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => setCurrentView(item.key)}
                aria-pressed={isActive}
                style={{
                  flex: 1,
                  height: '100%',
                  border: 'none',
                  background: 'transparent',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  color: isActive ? '#2c2c2c' : '#8a7a69',
                  fontSize: 11,
                  fontWeight: isActive ? 600 : 400,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  cursor: isActive ? 'default' : 'pointer'
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      )}

      {/* Warning Dialog */}
      {showWarning && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: '#fffef9',
            border: '2px solid #d0c4b0',
            borderRadius: '8px',
            padding: '32px',
            maxWidth: '400px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}>
            <h2 style={{
              margin: '0 0 16px 0',
              fontSize: '20px',
              color: '#333',
              fontWeight: 600
            }}>
              Start Fresh?
            </h2>
            <p style={{
              margin: '0 0 24px 0',
              fontSize: '16px',
              lineHeight: '1.6',
              color: '#555'
            }}>
              This will delete all your current writing and comments. This action cannot be undone.
            </p>
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={handleConfirmStartFresh}
                style={{
                  padding: '8px 20px',
                  border: '1px solid #d44',
                  background: '#d44',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: '#fff',
                  fontWeight: 600,
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#c33';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#d44';
                }}
              >
                Delete All
              </button>
              <button
                onClick={() => setShowWarning(false)}
                style={{
                  padding: '8px 20px',
                  border: '1px solid #d0c4b0',
                  background: '#fff',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: '#333',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#fff';
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Calendar Popup */}
      {showCalendarPopup && (
        <CalendarPopup
          onLoadEntry={handleLoadEntry}
          currentEntryId={state?.id}
          onEntryDeleted={handleCalendarEntryDeleted}
          onClose={() => setShowCalendarPopup(false)}
          timezone={userTimezone}
          initialDateKey={getLocalDayKey(state?.createdAt, userTimezone) ?? getTodayKeyInTimezone(userTimezone)}
        />
      )}
    </>
  );
}
