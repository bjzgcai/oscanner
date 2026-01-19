'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Space } from 'antd';
import { HomeOutlined, TeamOutlined } from '@ant-design/icons';

export default function Navigation() {
  const pathname = usePathname();

  const navItems = [
    { path: '/', label: 'Home', icon: <HomeOutlined /> },
    { path: '/repos', label: 'Multi-Repo Analysis', icon: <TeamOutlined /> },
  ];

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
  );
}
