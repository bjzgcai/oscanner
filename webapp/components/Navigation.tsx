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
      background: '#0A0A0A',
      borderBottom: '2px solid #333',
      padding: '15px 20px',
      position: 'sticky',
      top: 0,
      zIndex: 1000
    }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto', display: 'flex', alignItems: 'center', gap: '30px' }}>
        <div style={{
          fontSize: '20px',
          fontWeight: 'bold',
          color: '#FFEB00',
          marginRight: 'auto'
        }}>
          Engineer Skill Evaluator
        </div>

        <Space size="large">
          {navItems.map((item) => (
            <Link
              key={item.path}
              href={item.path}
              style={{
                color: pathname === item.path ? '#FFEB00' : '#B0B0B0',
                textDecoration: 'none',
                fontSize: '14px',
                fontWeight: pathname === item.path ? 'bold' : 'normal',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'color 0.3s',
                borderBottom: pathname === item.path ? '2px solid #FFEB00' : '2px solid transparent',
                paddingBottom: '3px'
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
