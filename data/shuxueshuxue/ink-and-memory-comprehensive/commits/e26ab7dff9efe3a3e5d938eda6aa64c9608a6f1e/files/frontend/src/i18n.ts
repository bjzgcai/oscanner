import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const LANGUAGE_STORAGE_KEY = 'ink-language';

const resources = {
  en: {
    translation: {
      nav: {
        writing: 'Writing',
        timeline: 'Timeline',
        analysis: 'Reflections',
        decks: 'Decks',
        settings: 'Settings'
      },
      settings: {
        heading: 'The Voice Council',
        subheading: 'Configure the inner voices that annotate everything you write.',
        tabs: {
          voices: '🎭 Voices',
          meta: '📜 Meta Prompt',
          states: '💭 User States'
        },
        language: {
          title: 'Interface Language',
          description: 'Choose which language the UI uses while your writing stays untouched.',
          placeholder: 'Select a language',
          preview: 'Changes apply immediately to menus, buttons, and helper copy.',
          options: {
            en: 'English',
            zh: '中文 (Chinese)'
          }
        }
      },
      analysis: {
        title: 'Reflections',
        subtitle: 'Patterns and insights woven through your words',
        backButton: 'Back',
        backTitle: 'Back to Dashboard',
        stats: {
          days: 'Days',
          entries: 'Entries',
          words: 'Words'
        },
        pastReflections: 'Past Reflections',
        report: {
          patternCount: '{{count}} patterns'
        },
        actions: {
          generate: 'Generate New Analysis',
          generating: 'Reflecting...'
        },
        empty: {
          title: 'Your story awaits analysis',
          description: 'Begin the journey to discover the patterns, themes, and essence woven through your words'
        }
      },
      deck: {
        heading: 'Voice Decks',
        subheading: 'Organize your inner voices into thematic collections',
        actions: {
          retry: 'Retry',
          create: '+ Create New Deck',
          creating: 'Creating...',
          addVoice: '+ Add Voice to this Deck',
          addingVoice: 'Adding...',
          install: 'Install',
          sync: 'Sync with Original',
          publish: 'Publish to Community',
          unpublish: 'Unpublish',
          delete: 'Delete Deck'
        },
        sections: {
          myDecks: 'My Decks',
          community: 'Community Decks ({{count}})'
        },
        labels: {
          system: 'System',
          noDescription: 'No description',
          voiceCount: '{{count}} voices',
          anonymous: 'Anonymous'
        },
        communityMeta: 'by {{author}} · {{voices}} voices · {{installs}} installs',
        communityEmpty: 'No published decks yet. Be the first to share!',
        confirm: {
          delete: 'Delete this deck and all its voices?',
          sync: 'Sync with original template? This will overwrite any changes you made to this deck.'
        }
      },
      timeline: {
        today: 'Today',
        generating: 'Generating...',
        entryCount_one: '{{count}} entry',
        entryCount_other: '{{count}} entries'
      }
    }
  },
  zh: {
    translation: {
      nav: {
        writing: '写作',
        timeline: '时间线',
        analysis: '回顾',
        decks: '卡组',
        settings: '设置'
      },
      settings: {
        heading: '心灵议会',
        subheading: '在这里整理那些会对你文字发表评论的声音。',
        tabs: {
          voices: '🎭 声线',
          meta: '📜 元提示',
          states: '💭 心情状态'
        },
        language: {
          title: '界面语言',
          description: '切换界面上的文字语言，日记内容保持原样。',
          placeholder: '选择语言',
          preview: '切换后菜单、按钮与说明会立即更新。',
          options: {
            en: 'English (英语)',
            zh: '中文'
          }
        }
      },
      analysis: {
        title: '回顾',
        subtitle: '读出文字里编织的脉络与启示',
        backButton: '返回',
        backTitle: '回到总览',
        stats: {
          days: '天数',
          entries: '篇章',
          words: '字数'
        },
        pastReflections: '历史回顾',
        report: {
          patternCount: '{{count}} 个模式'
        },
        actions: {
          generate: '生成全新分析',
          generating: '解析中...'
        },
        empty: {
          title: '等待解析的故事',
          description: '开始探索文字里反复出现的主题、情绪与线索'
        }
      },
      deck: {
          heading: '声线卡组',
          subheading: '以主题整理你的心灵声线',
          actions: {
            retry: '重试',
            create: '+ 新建卡组',
            creating: '建立中...',
            addVoice: '+ 向卡组添加声线',
            addingVoice: '添加中...',
            install: '安装',
            sync: '与原版同步',
            publish: '发布到社区',
            unpublish: '取消发布',
            delete: '删除卡组'
          },
        sections: {
          myDecks: '我的卡组',
          community: '社区卡组（{{count}}）'
        },
        labels: {
          system: '系统',
          noDescription: '暂无简介',
          voiceCount: '{{count}} 条声线',
          anonymous: '匿名'
        },
        communityMeta: '由 {{author}} 创作 · {{voices}} 条声线 · {{installs}} 次安装',
        communityEmpty: '尚无公开卡组，来做第一位分享的人吧！',
        confirm: {
          delete: '确定删除这个卡组以及所有声线？',
          sync: '与原模板同步？这会覆盖你在卡组里的修改。'
        }
      },
      timeline: {
        today: '今天',
        generating: '生成中...',
        entryCount_one: '{{count}} 条记录',
        entryCount_other: '{{count}} 条记录'
      }
    }
  }
};

const fallback = 'en';

function getInitialLanguage(): string {
  if (typeof window === 'undefined') {
    return fallback;
  }
  return localStorage.getItem(LANGUAGE_STORAGE_KEY) || fallback;
}

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: getInitialLanguage(),
    fallbackLng: fallback,
    interpolation: {
      escapeValue: false
    }
  });

if (typeof window !== 'undefined') {
  i18n.on('languageChanged', (lng) => {
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
    } catch (error) {
      console.warn('Failed to persist language preference:', error);
    }
  });
}

export { LANGUAGE_STORAGE_KEY };
export function getDateLocale(language?: string | null): string {
  if (!language) return 'en-US';
  return language.startsWith('zh') ? 'zh-CN' : 'en-US';
}

export default i18n;
