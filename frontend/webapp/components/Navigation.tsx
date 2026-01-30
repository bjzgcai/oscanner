'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Space, Button, Dropdown, Switch, Tooltip } from 'antd';
import { HomeOutlined, ApiOutlined, CheckCircleOutlined, SettingOutlined, RiseOutlined, CodeOutlined } from '@ant-design/icons';
import { useAppSettings } from './AppSettingsContext';
import { getApiBaseUrl } from '../utils/apiBase';
import { LOCALES } from '../i18n';
import { useI18n } from './I18nContext';

export default function Navigation() {
  const pathname = usePathname();
  const { useCache, setUseCache, model, setModel, pluginId, setPluginId, plugins, locale, setLocale, setLlmModalOpen } = useAppSettings();
  const { t } = useI18n();

  const navItems = [
    // Hidden pages (not removed, just not displayed in navigation)
    // { path: '/settings', label: t('nav.settings'), icon: <SettingOutlined /> },
    // { path: '/', label: t('nav.analysis'), icon: <HomeOutlined /> },
    // { path: '/validation', label: t('nav.validation'), icon: <CheckCircleOutlined /> },
    { path: '/trajectory', label: t('nav.trajectory'), icon: <RiseOutlined /> },
    { path: '/runner', label: 'Repository Runner', icon: <CodeOutlined /> },
  ];

  // Show config controls only on analysis and validation pages
  const showConfigControls = pathname === '/' || pathname === '/validation';

  // API docs URL points to backend /docs endpoint
  const apiBase = getApiBaseUrl();
  const apiDocsHref = apiBase ? `${apiBase}/docs` : '/docs';

  const modelItems = [
    { key: 'anthropic/claude-sonnet-4.5', label: 'Claude Sonnet 4.5' },
    { key: 'z-ai/glm-4.7', label: 'Z.AI GLM 4.7' },
    { key: 'qwen/qwen3-coder-flash', label: 'Qwen: Qwen3 Coder Flash' },
  ];
  const currentModelLabel = modelItems.find((i) => i.key === model)?.label || model;

  const pluginItems =
    plugins && plugins.length > 0
      ? plugins.map((p) => ({
          key: p.id,
          label: `${p.name}${p.version ? ` (${p.version})` : ''}`,
        }))
      : [
          { key: 'zgc_simple', label: 'ZGC Simple (Default)' },
          { key: 'zgc_ai_native_2026', label: 'ZGC AI-Native 2026' },
        ];
  const currentPluginLabel = (plugins || []).find((p) => p.id === pluginId)?.name || pluginId || 'zgc_simple';

  return (
    <>
      <nav style={{
        background: '#FFFFFF',
        borderBottom: '1px solid #E5E7EB',
        padding: '16px 24px',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
        boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'flex', alignItems: 'center', gap: '32px' }}>
          <div style={{
            fontSize: '18px',
            fontWeight: '700',
            color: '#111827',
            marginRight: 'auto',
            letterSpacing: '-0.01em'
          }}>
            {t('nav.title')}
          </div>

          <Space size="large">
            {navItems.map((item) => (
              <Link
                key={item.path}
                href={item.path}
                style={{
                  color: pathname === item.path ? '#1E40AF' : '#6B7280',
                  textDecoration: 'none',
                  fontSize: '14px',
                  fontWeight: pathname === item.path ? '600' : '500',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'color 0.2s',
                  borderBottom: pathname === item.path ? '2px solid #1E40AF' : '2px solid transparent',
                  paddingBottom: '4px'
                }}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            ))}
          </Space>
        </div>
      </nav>

      {showConfigControls && (
        <div style={{
          background: '#F9FAFB',
          borderBottom: '1px solid #E5E7EB',
          padding: '12px 24px',
          position: 'sticky',
          top: '72px',
          zIndex: 999
        }}>
          <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'flex', alignItems: 'center', gap: '16px', justifyContent: 'flex-end' }}>
            <Tooltip title={t('nav.cache.tooltip')}>
              <Switch
                checked={useCache}
                onChange={setUseCache}
                checkedChildren={t('nav.cache.on')}
                unCheckedChildren={t('nav.cache.off')}
              />
            </Tooltip>

            <Dropdown
              menu={{
                items: LOCALES.map((l) => ({ key: l.key, label: l.label })),
                selectable: true,
                selectedKeys: [locale],
                onClick: ({ key }) => setLocale(String(key) as typeof locale),
              }}
              trigger={['click']}
            >
              <Button size="middle">
                {t('nav.language')}: {LOCALES.find((l) => l.key === locale)?.label || locale}
              </Button>
            </Dropdown>

            <Dropdown
              menu={{
                items: pluginItems,
                selectable: true,
                selectedKeys: [pluginId || 'zgc_simple'],
                onClick: ({ key }) => setPluginId(String(key)),
              }}
              trigger={['click']}
            >
              <Button size="middle">
                {t('nav.plugin')}: {currentPluginLabel}
              </Button>
            </Dropdown>

            <Dropdown
              menu={{
                items: modelItems,
                selectable: true,
                selectedKeys: [model],
                onClick: ({ key }) => setModel(String(key)),
              }}
              trigger={['click']}
            >
              <Button size="middle">
                {t('nav.model')}: {currentModelLabel}
              </Button>
            </Dropdown>

            <Button
              icon={<SettingOutlined />}
              size="middle"
              onClick={() => setLlmModalOpen(true)}
            >
              {t('nav.llm_settings')}
            </Button>

            <a href={apiDocsHref} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
              <Button icon={<ApiOutlined />} size="middle">
                {t('nav.api')}
              </Button>
            </a>
          </div>
        </div>
      )}
    </>
  );
}
