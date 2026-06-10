import React from 'react';
import { StandardCompareView } from '../../_shared/view/StandardRubricViews';
import type { PluginMultiRepoCompareViewProps } from '../../_shared/view/types';

const config = {
  pluginId: 'tsia057_ai_agent_engineer_2026',
  title: 'T/SIA 057-2026 AI Agent Engineer',
  subtitle: '12 TSIA057 competency dimensions across repositories',
  accent: '#0F766E',
};

export default function TSIA057CompareView(props: PluginMultiRepoCompareViewProps) {
  return <StandardCompareView {...props} config={config} />;
}
