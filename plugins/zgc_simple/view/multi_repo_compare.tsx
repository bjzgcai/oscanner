import React from 'react';
import { Card, Tag } from 'antd';
import ContributorComparisonBase from '../../_shared/view/ContributorComparisonBase';
import type { PluginMultiRepoCompareViewProps } from '../../_shared/view/types';

export default function CompareView(props: PluginMultiRepoCompareViewProps) {
  const { data, loading, error, t: tFromProps } = props;
  if (typeof tFromProps !== 'function') {
    throw new Error('zgc_simple plugin compare view requires `t(key, params?)` prop from host app.');
  }
  const t = tFromProps;
  const pluginUsed = data?.plugin_used || 'zgc_simple';
  const pluginVersion = data?.comparisons?.[0]?.plugin_version || '';

  return (
    <Card
      style={{
        border: '3px solid #22D3EE',
        background: 'linear-gradient(180deg, #06202A 0%, #0B1220 60%, #0A0F1C 100%)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ color: '#22D3EE', fontWeight: 900, letterSpacing: 0.2, fontSize: 18 }}>
            {t('plugin.zgc_simple.compare.title')}
          </div>
          <div style={{ color: '#9CA3AF', fontSize: 12, marginTop: 4 }}>
            {t('plugin.zgc_simple.compare.banner.active')}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Tag color="cyan" style={{ fontWeight: 900 }}>
            {t('plugin.zgc_simple.compare.tag.active')}
          </Tag>
          <Tag color="gold" style={{ fontWeight: 900 }}>
            plugin={pluginUsed}
            {pluginVersion ? ` @ ${pluginVersion}` : ''}
          </Tag>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <ContributorComparisonBase data={data} loading={loading} error={error} theme="simple" />
      </div>
    </Card>
  );
}


