'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Space, Button, Switch, Tooltip, Dropdown } from 'antd';
import { HomeOutlined, ApiOutlined } from '@ant-design/icons';
import { useAppSettings } from './AppSettingsContext';

export default function Navigation() {
  const pathname = usePathname();
  const { useCache, setUseCache, model, setModel } = useAppSettings();

  const navItems = [
    { path: '/', label: 'Analysis', icon: <HomeOutlined /> },
  ];

  // Prefer explicit backend URL in dev/standalone mode; otherwise default to same-origin.
  const apiBase = (process.env.NEXT_PUBLIC_API_SERVER_URL || '').replace(/\/$/, '');
  const apiHref = apiBase ? `${apiBase}/` : '/';

  const modelItems = [
    { key: 'anthropic/claude-sonnet-4.5', label: 'Claude Sonnet 4.5' },
    { key: 'z-ai/glm-4.7', label: 'Z.AI GLM 4.7' },
  ];
  const currentModelLabel = modelItems.find((i) => i.key === model)?.label || model;

  return (
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
          Engineer Skill Evaluator
        </div>

        <Space size="large">
          <Tooltip title="启用后优先返回历史评估结果；不启用则强制重新评估（需要配置 LLM Key）。">
            <Switch
              checked={useCache}
              onChange={setUseCache}
              checkedChildren="cache"
              unCheckedChildren="no cache"
            />
          </Tooltip>

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
              Model: {currentModelLabel}
            </Button>
          </Dropdown>

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

          <a href={apiHref} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
            <Button icon={<ApiOutlined />} size="middle">
              API
            </Button>
          </a>
        </Space>
      </div>
    </nav>
  );
}
