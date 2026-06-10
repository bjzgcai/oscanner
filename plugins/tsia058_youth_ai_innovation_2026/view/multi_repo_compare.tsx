import React from 'react';
import { StandardCompareView } from '../../_shared/view/StandardRubricViews';
import type { PluginMultiRepoCompareViewProps } from '../../_shared/view/types';

const config = {
  pluginId: 'tsia058_youth_ai_innovation_2026',
  title: 'T/SIA 058-2026 Youth AI Innovation',
  subtitle: '12 youth AI application and innovation dimensions across repositories',
  accent: '#B45309',
};

export default function TSIA058CompareView(props: PluginMultiRepoCompareViewProps) {
  return <StandardCompareView {...props} config={config} />;
}
