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
        friends: 'Friends',
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
          latest: 'Latest',
          patternCount: '{{count}} patterns'
        },
        actions: {
          generate: 'Generate New Analysis',
          generating: 'Reflecting...'
        },
        empty: {
          title: 'Your story awaits analysis',
          description: 'Begin the journey to discover the patterns, themes, and essence woven through your words'
        },
        papers: {
          echoes: { title: 'Recurring Themes', subtitle: 'Echoes' },
          traits: { title: 'Character Traits', subtitle: 'Personality' },
          patterns: { title: 'Behavioral Patterns', subtitle: 'Habits' }
        },
        statsLabels: {
          daysCount_one: '{{count}} day',
          daysCount_other: '{{count}} days',
          entriesCount_one: '{{count}} entry',
          entriesCount_other: '{{count}} entries',
          wordsCount: '{{value}} words'
        },
        reportCounts: {
          echoes_one: '{{count}} echo',
          echoes_other: '{{count}} echoes',
          traits_one: '{{count}} trait',
          traits_other: '{{count}} traits',
          patterns_one: '{{count}} pattern',
          patterns_other: '{{count}} patterns'
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
        },
        publishWarning: {
          heading: '⚠️ Publish Deck Warning',
          body: 'Publishing will <strong>break the parent link</strong>. This deck becomes a standalone deck in the community store.',
          note: 'This action cannot be undone. Even if you unpublish later, the parent link stays broken.',
          cancel: 'Cancel',
          confirm: 'Publish Anyway'
        },
        messages: {
          publishSuccess: '✅ Deck published to community!',
          unpublishSuccess: '✅ Deck unpublished',
          installSuccess: '✅ Deck installed to your collection!'
        }
      },
      timeline: {
        today: 'Today',
        generating: 'Generating...',
        entryCount_one: '{{count}} entry',
        entryCount_other: '{{count}} entries',
        friendSelector: {
          label: 'View Timeline',
          placeholder: 'Choose a friend',
          none: 'No friend selected',
          loading: 'Loading friends...',
          error: 'Could not load friends',
          button: 'Timeline settings',
          summarySolo: 'Personal timeline only',
          summaryWithFriend: 'Comparing with {{name}}',
          searchPlaceholder: 'Search friends',
          noFriends: 'You have no friends yet.',
          noMatches: 'No matches found',
          close: 'Close',
          personal: 'You',
          more: 'More'
        },
        friendTimeline: {
          loading: 'Loading friend timeline...',
          empty: 'This friend has no entries yet.',
          error: 'Unable to load friend timeline.',
          readOnly: "Friend reflections open in read-only mode. You're just viewing their day.",
          readOnlyShort: 'Friend timeline preview'
        }
      },
      timelinePlaceholders: {
        today: 'Generates automatically overnight',
        '-7': 'Taste buds renew every 10 days',
        '-6': 'The liver regenerates in 6 weeks',
        '-5': 'Stomach lining replaces itself every 5 days',
        '-4': 'Skin cells shed every 2–4 weeks',
        '-3': 'Red blood cells live for 120 days',
        '-2': 'The heart beats 100,000 times a day',
        '-1': 'Neurons can form new connections',
        '1': 'Tomorrow is unwritten',
        '2': 'The future is a blank page',
        default: 'Nothing captured yet'
      },
      calendar: {
        title: 'Calendar',
        subtitle: 'Select a day to revisit your entries',
        empty: 'No entries yet. Start writing to fill this calendar.',
        deleteConfirm: 'Delete this entry?',
        entriesLabel_one: '{{count}} entry',
        entriesLabel_other: '{{count}} entries',
        openButton: 'Open',
        deleteButton: 'Delete',
        close: 'Close',
        prev: '← Prev',
        next: 'Next →',
        noEntriesForDate: 'No entries for this date',
        todayLabel: 'Today',
        deleteError: 'Failed to delete entry'
      },
      friends: {
        myFriends: 'My Friends',
        requests: 'Requests',
        addFriend: 'Add Friend',
        noFriends: 'No friends yet. Use an invite code to add your first friend!',
        noRequests: 'No pending friend requests',
        loading: 'Loading...',
        viewTimeline: 'View Timeline',
        remove: 'Remove',
        accept: 'Accept',
        reject: 'Reject',
        generateInvite: 'Generate Invite Code',
        generateHint: 'Share this code with someone to let them send you a friend request. Code expires in 7 days.',
        generate: 'Generate Code',
        generating: 'Generating...',
        copy: 'Copy',
        codeCopied: 'Code copied to clipboard!',
        expiresAt: 'Expires',
        useInvite: 'Use Invite Code',
        useHint: 'Enter a friend\'s invite code to send them a friend request.',
        codePlaceholder: 'Enter 6-character code',
        send: 'Send Request',
        sending: 'Sending...',
        requestSent: 'Friend request sent!',
        confirmRemove: 'Remove this friend?',
        generateError: 'Failed to generate invite code',
        useCodeError: 'Invalid or expired code',
        acceptError: 'Failed to accept request',
        rejectError: 'Failed to reject request',
        removeError: 'Failed to remove friend'
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
        friends: '好友',
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
          latest: '最新',
          patternCount: '{{count}} 个模式'
        },
        actions: {
          generate: '生成全新分析',
          generating: '解析中...'
        },
        empty: {
          title: '等待解析的故事',
          description: '开始探索文字里反复出现的主题、情绪与线索'
        },
        papers: {
          echoes: { title: '重复回响', subtitle: '主题回声' },
          traits: { title: '性格折射', subtitle: '个性印象' },
          patterns: { title: '行为轨迹', subtitle: '惯性与习惯' }
        },
        statsLabels: {
          daysCount_one: '{{count}} 天',
          daysCount_other: '{{count}} 天',
          entriesCount_one: '{{count}} 篇章',
          entriesCount_other: '{{count}} 篇章',
          wordsCount: '{{value}} 字'
        },
        reportCounts: {
          echoes_one: '{{count}} 个回声',
          echoes_other: '{{count}} 个回声',
          traits_one: '{{count}} 个性格',
          traits_other: '{{count}} 个性格',
          patterns_one: '{{count}} 个模式',
          patterns_other: '{{count}} 个模式'
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
        },
        publishWarning: {
          heading: '⚠️ 发布提醒',
          body: '发布后会<strong>断开与父卡组的链接</strong>，并在社区中以独立卡组存在。',
          note: '此操作不可逆，就算之后取消发布，父子链接也无法恢复。',
          cancel: '取消',
          confirm: '仍要发布'
        },
        messages: {
          publishSuccess: '✅ 已发布到社区！',
          unpublishSuccess: '✅ 已取消发布',
          installSuccess: '✅ 已安装到你的卡组'
        }
      },
      timeline: {
        today: '今天',
        generating: '生成中...',
        entryCount_one: '{{count}} 条记录',
        entryCount_other: '{{count}} 条记录',
        friendSelector: {
          label: '查看时间线',
          placeholder: '选择好友',
          none: '不查看好友',
          loading: '正在加载好友...',
          error: '无法加载好友列表',
          button: '时间线设置',
          summarySolo: '当前仅显示个人时间线',
          summaryWithFriend: '正在与 {{name}} 的时间线对照',
          searchPlaceholder: '搜索好友',
          noFriends: '你还没有好友。',
          noMatches: '没有符合条件的好友',
          close: '关闭',
          personal: '仅自己',
          more: '更多'
        },
        friendTimeline: {
          loading: '正在加载好友时间线...',
          empty: '这位好友最近没有记录。',
          error: '无法加载好友的时间线。',
          readOnly: '好友的总结仅供查看，无法互动。',
          readOnlyShort: '好友时间线预览'
        }
      },
      timelinePlaceholders: {
        today: '夜里自动生成你的时间线',
        '-7': '味蕾每 10 天更新一次',
        '-6': '肝脏在 6 周内自我修复',
        '-5': '胃黏膜大约 5 天换新',
        '-4': '皮肤每 2-4 周脱落再生',
        '-3': '红细胞寿命约 120 天',
        '-2': '心脏每天跳动 10 万次',
        '-1': '神经元随时能建立新连接',
        '1': '明天还没被书写',
        '2': '未来是一张空白页',
        default: '这里还没有记录'
      },
      calendar: {
        title: '日历',
        subtitle: '选择任意一天重新回到当时的文字',
        empty: '这里还没有记录，动笔就会留下足迹。',
        deleteConfirm: '确定删除这篇记录？',
        entriesLabel_one: '{{count}} 篇',
        entriesLabel_other: '{{count}} 篇',
        openButton: '打开',
        deleteButton: '删除',
        close: '关闭',
        prev: '← 上个月',
        next: '下个月 →',
        noEntriesForDate: '这一天暂无记录',
        todayLabel: '今天',
        deleteError: '删除失败'
      },
      friends: {
        myFriends: '我的好友',
        requests: '好友申请',
        addFriend: '添加好友',
        noFriends: '还没有好友。使用邀请码添加你的第一个好友吧！',
        noRequests: '暂无待处理的好友申请',
        loading: '加载中...',
        viewTimeline: '查看时间线',
        remove: '移除',
        accept: '接受',
        reject: '拒绝',
        generateInvite: '生成邀请码',
        generateHint: '将此邀请码分享给朋友，让对方向你发送好友申请。邀请码 7 天后过期。',
        generate: '生成邀请码',
        generating: '生成中...',
        copy: '复制',
        codeCopied: '邀请码已复制到剪贴板！',
        expiresAt: '过期时间',
        useInvite: '使用邀请码',
        useHint: '输入朋友的邀请码，向对方发送好友申请。',
        codePlaceholder: '输入 6 位邀请码',
        send: '发送申请',
        sending: '发送中...',
        requestSent: '好友申请已发送！',
        confirmRemove: '确定要移除这位好友吗？',
        generateError: '生成邀请码失败',
        useCodeError: '邀请码无效或已过期',
        acceptError: '接受申请失败',
        rejectError: '拒绝申请失败',
        removeError: '移除好友失败'
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
