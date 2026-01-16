'use client';

import { useState, useRef, useEffect } from 'react';
import { Card, Radio, Spin, Empty, Alert, Space } from 'antd';
import { RadarChartOutlined, BarChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';

interface Score {
  ai_model_fullstack: number;
  ai_native_architecture: number;
  cloud_native: number;
  open_source_collaboration: number;
  intelligent_development: number;
  engineering_leadership: number;
}

interface Comparison {
  repo: string;
  owner: string;
  repo_name: string;
  scores: Score;
  total_commits: number;
  cached: boolean;
}

interface ContributorComparisonData {
  success: boolean;
  contributor: string;
  comparisons: Comparison[];
  dimension_keys: string[];
  dimension_names: string[];
  aggregate: {
    total_repos_evaluated: number;
    total_commits: number;
    average_scores: Score;
  };
  failed_repos?: Array<{ repo: string; reason: string }>;
}

interface ContributorComparisonProps {
  data: ContributorComparisonData | null;
  loading?: boolean;
  error?: string;
}

type ChartType = 'radar' | 'bar';

export default function ContributorComparison({
  data,
  loading = false,
  error
}: ContributorComparisonProps) {
  const [chartType, setChartType] = useState<ChartType>('radar');
  const chartRef = useRef<any>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chartRef.current) {
        const echartsInstance = chartRef.current.getEchartsInstance();
        if (echartsInstance) {
          try {
            echartsInstance.dispose();
          } catch (e) {
            // Silently handle disposal errors
          }
        }
      }
    };
  }, []);

  if (loading) {
    return (
      <Card
        style={{
          background: '#1A1A1A',
          border: '3px solid #333',
          borderRadius: '0',
          textAlign: 'center',
          padding: '60px 20px'
        }}
      >
        <Spin size="large" />
        <div style={{ color: '#B0B0B0', marginTop: '20px' }}>
          Evaluating contributor across repositories...
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert
        message="Error"
        description={error}
        type="error"
        showIcon
        style={{
          background: '#2A0A0A',
          border: '2px solid #FF006B',
          borderRadius: '0',
          color: '#FF006B'
        }}
      />
    );
  }

  if (!data || !data.success || !data.comparisons || data.comparisons.length === 0) {
    return (
      <Card
        style={{
          background: '#1A1A1A',
          border: '3px solid #333',
          borderRadius: '0',
          textAlign: 'center',
          padding: '60px 20px'
        }}
      >
        <Empty
          description={
            <span style={{ color: '#B0B0B0' }}>
              No comparison data available
            </span>
          }
        />
      </Card>
    );
  }

  // Prepare data for charts
  const dimensionNames = data.dimension_names.map(name => {
    // Shorten dimension names for better display
    return name.replace(' & ', '\n').replace('Capability', '').trim();
  });

  const shortDimensionNames = [
    'AI Model\nFull-Stack',
    'AI Native\nArchitecture',
    'Cloud\nNative',
    'Open Source\nCollaboration',
    'Intelligent\nDevelopment',
    'Engineering\nLeadership'
  ];

  const colors = ['#FFEB00', '#00F0FF', '#FF006B', '#00FF87', '#FF8C00', '#9D4EDD'];

  // Get radar chart options
  const getRadarOptions = () => {
    const seriesData = data.comparisons.map((comp, idx) => ({
      name: comp.repo,
      value: Object.values(comp.scores),
      itemStyle: {
        color: colors[idx % colors.length]
      }
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#1A1A1A',
        borderColor: '#333',
        borderWidth: 2,
        textStyle: {
          color: '#FFFFFF'
        }
      },
      legend: {
        data: data.comparisons.map(c => c.repo),
        bottom: 10,
        textStyle: {
          color: '#FFFFFF',
          fontSize: 12
        }
      },
      radar: {
        indicator: shortDimensionNames.map((name, idx) => ({
          name: name,
          max: 100,
          color: '#FFFFFF'
        })),
        splitArea: {
          areaStyle: {
            color: ['rgba(255, 235, 0, 0.05)', 'rgba(255, 235, 0, 0.1)']
          }
        },
        splitLine: {
          lineStyle: {
            color: '#333'
          }
        },
        axisLine: {
          lineStyle: {
            color: '#333'
          }
        },
        name: {
          textStyle: {
            color: '#FFFFFF',
            fontSize: 11,
            fontWeight: 'bold'
          }
        }
      },
      series: [
        {
          type: 'radar',
          data: seriesData,
          lineStyle: {
            width: 2
          },
          areaStyle: {
            opacity: 0.3
          }
        }
      ]
    };
  };

  // Get grouped bar chart options
  const getBarOptions = () => {
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        },
        backgroundColor: '#1A1A1A',
        borderColor: '#333',
        borderWidth: 2,
        textStyle: {
          color: '#FFFFFF'
        }
      },
      legend: {
        data: data.comparisons.map(c => c.repo),
        bottom: 10,
        textStyle: {
          color: '#FFFFFF',
          fontSize: 12
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '5%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: shortDimensionNames,
        axisLabel: {
          color: '#FFFFFF',
          fontSize: 10,
          interval: 0,
          rotate: 0
        },
        axisLine: {
          lineStyle: {
            color: '#333'
          }
        }
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLabel: {
          color: '#FFFFFF'
        },
        splitLine: {
          lineStyle: {
            color: '#333'
          }
        }
      },
      series: data.comparisons.map((comp, idx) => ({
        name: comp.repo,
        type: 'bar',
        data: Object.values(comp.scores),
        itemStyle: {
          color: colors[idx % colors.length]
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: colors[idx % colors.length]
          }
        }
      }))
    };
  };


  const getChartOptions = () => {
    switch (chartType) {
      case 'radar':
        return getRadarOptions();
      case 'bar':
        return getBarOptions();
      default:
        return getRadarOptions();
    }
  };

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#FFEB00', fontSize: '20px', fontWeight: 'bold' }}>
            {data.contributor} - Six-Dimensional Capability Comparison
          </span>
          <Radio.Group
            value={chartType}
            onChange={(e) => setChartType(e.target.value)}
            buttonStyle="solid"
          >
            <Radio.Button value="radar">
              <RadarChartOutlined /> Radar
            </Radio.Button>
            <Radio.Button value="bar">
              <BarChartOutlined /> Bar
            </Radio.Button>
          </Radio.Group>
        </div>
      }
      style={{
        background: '#1A1A1A',
        border: '3px solid #FFEB00',
        borderRadius: '0'
      }}
      headStyle={{
        background: '#0A0A0A',
        border: 'none',
        borderBottom: '2px solid #FFEB00'
      }}
    >
      {/* Chart */}
      <div style={{ marginBottom: '30px' }}>
        <ReactECharts
          ref={chartRef}
          option={getChartOptions()}
          style={{ height: '500px', width: '100%' }}
          theme="dark"
          notMerge={true}
          lazyUpdate={true}
          opts={{ renderer: 'canvas' }}
        />
      </div>

      {/* Aggregate Statistics */}
      <div
        style={{
          background: '#0A0A0A',
          border: '2px solid #333',
          padding: '20px',
          marginTop: '20px'
        }}
      >
        <h3 style={{ color: '#00F0FF', marginBottom: '15px', fontSize: '16px' }}>
          Aggregate Statistics
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
          <div>
            <div style={{ color: '#B0B0B0', fontSize: '12px' }}>Total Repositories</div>
            <div style={{ color: '#FFFFFF', fontSize: '24px', fontWeight: 'bold' }}>
              {data.aggregate.total_repos_evaluated}
            </div>
          </div>
          <div>
            <div style={{ color: '#B0B0B0', fontSize: '12px' }}>Total Commits</div>
            <div style={{ color: '#FFEB00', fontSize: '24px', fontWeight: 'bold' }}>
              {data.aggregate.total_commits}
            </div>
          </div>
          {Object.entries(data.aggregate.average_scores).map(([key, value], idx) => (
            <div key={key}>
              <div style={{ color: '#B0B0B0', fontSize: '12px' }}>
                Avg {data.dimension_names[idx]?.split('&')[0]?.trim()}
              </div>
              <div style={{ color: colors[idx % colors.length], fontSize: '20px', fontWeight: 'bold' }}>
                {value.toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Repository Details */}
      <div style={{ marginTop: '30px' }}>
        <h3 style={{ color: '#00F0FF', marginBottom: '15px', fontSize: '16px' }}>
          Repository Details
        </h3>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {data.comparisons.map((comp, idx) => (
            <div
              key={comp.repo}
              style={{
                background: '#0A0A0A',
                border: `2px solid ${colors[idx % colors.length]}`,
                padding: '15px'
              }}
            >
              <div style={{ marginBottom: '10px' }}>
                <span style={{ color: colors[idx % colors.length], fontSize: '16px', fontWeight: 'bold' }}>
                  {comp.repo}
                </span>
                <span style={{ color: '#B0B0B0', marginLeft: '15px' }}>
                  {comp.total_commits} commits analyzed
                </span>
                {comp.cached && (
                  <span style={{ color: '#52c41a', marginLeft: '10px', fontSize: '12px' }}>
                    ⚡ Cached
                  </span>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
                {Object.entries(comp.scores).map(([key, value], dimIdx) => (
                  <div key={key} style={{ fontSize: '12px' }}>
                    <span style={{ color: '#B0B0B0' }}>
                      {data.dimension_names[dimIdx]?.split('&')[0]?.trim()}:{' '}
                    </span>
                    <span style={{ color: '#FFFFFF', fontWeight: 'bold' }}>
                      {value.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </Space>
      </div>

      {/* Failed Repos Warning */}
      {data.failed_repos && data.failed_repos.length > 0 && (
        <Alert
          message="Some repositories failed"
          description={
            <ul style={{ margin: '10px 0 0 0', paddingLeft: '20px' }}>
              {data.failed_repos.map((failed, idx) => (
                <li key={idx} style={{ color: '#B0B0B0' }}>
                  {failed.repo}: {failed.reason}
                </li>
              ))}
            </ul>
          }
          type="warning"
          showIcon
          style={{
            marginTop: '20px',
            background: '#2A1A0A',
            border: '2px solid #faad14',
            borderRadius: '0'
          }}
        />
      )}
    </Card>
  );
}
