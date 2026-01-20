'use client';

import { useState, useRef, useEffect } from 'react';
import { Card, Radio, Spin, Empty, Alert, Space, Descriptions } from 'antd';
import { RadarChartOutlined, BarChartOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import type EChartsReact from 'echarts-for-react';
import type { ContributorComparisonData } from '../types';

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
  const chartRef = useRef<EChartsReact | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    const current = chartRef.current;
    return () => {
      if (current) {
          try {
          current.getEchartsInstance()?.dispose();
          } catch {
            // Silently handle disposal errors
        }
      }
    };
  }, []);

  if (loading) {
    return (
      <Card
        style={{ textAlign: 'center', padding: '60px 20px' }}
      >
        <Spin size="large" />
        <div style={{ color: 'rgba(0, 0, 0, 0.65)', marginTop: '20px' }}>
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
        style={{ borderRadius: 8 }}
      />
    );
  }

  if (!data || !data.success || !data.comparisons || data.comparisons.length === 0) {
    return (
      <Card
        style={{ textAlign: 'center', padding: '60px 20px' }}
      >
        <Empty
          description={
            <span style={{ color: 'rgba(0, 0, 0, 0.65)' }}>
              No comparison data available
            </span>
          }
        />
      </Card>
    );
  }

  // Prepare data for charts
  const shortDimensionNames = [
    'AI Model\nFull-Stack',
    'AI Native\nArchitecture',
    'Cloud\nNative',
    'Open Source\nCollaboration',
    'Intelligent\nDevelopment',
    'Engineering\nLeadership'
  ];

  // Light-theme friendly palette (Ant Design-ish)
  const colors = ['#1E40AF', '#0891B2', '#059669', '#D97706', '#DC2626', '#6D28D9'];

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
        backgroundColor: '#ffffff',
        borderColor: '#d9d9d9',
        borderWidth: 1,
        textStyle: {
          color: 'rgba(0, 0, 0, 0.85)'
        }
      },
      legend: {
        data: data.comparisons.map(c => c.repo),
        bottom: 10,
        textStyle: {
          color: 'rgba(0, 0, 0, 0.85)',
          fontSize: 12
        }
      },
      radar: {
        indicator: shortDimensionNames.map((name) => ({
          name: name,
          max: 100,
          color: 'rgba(0, 0, 0, 0.85)'
        })),
        splitArea: {
          areaStyle: {
            color: ['rgba(0, 0, 0, 0.02)', 'rgba(0, 0, 0, 0.04)']
          }
        },
        splitLine: {
          lineStyle: {
            color: '#d9d9d9'
          }
        },
        axisLine: {
          lineStyle: {
            color: '#d9d9d9'
          }
        },
        name: {
          textStyle: {
            color: 'rgba(0, 0, 0, 0.85)',
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
        backgroundColor: '#ffffff',
        borderColor: '#d9d9d9',
        borderWidth: 1,
        textStyle: {
          color: 'rgba(0, 0, 0, 0.85)'
        }
      },
      legend: {
        data: data.comparisons.map(c => c.repo),
        bottom: 10,
        textStyle: {
          color: 'rgba(0, 0, 0, 0.85)',
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
          color: 'rgba(0, 0, 0, 0.85)',
          fontSize: 10,
          interval: 0,
          rotate: 0
        },
        axisLine: {
          lineStyle: {
            color: '#d9d9d9'
          }
        }
      },
      yAxis: {
        type: 'value',
        max: 100,
        axisLabel: {
          color: 'rgba(0, 0, 0, 0.85)'
        },
        splitLine: {
          lineStyle: {
            color: '#f0f0f0'
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
          <span style={{ fontSize: '18px', fontWeight: 'bold' }}>
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
    >
      {/* Chart */}
      <div style={{ marginBottom: '30px' }} id="comparison-chart-export">
        <ReactECharts
          ref={chartRef}
          option={getChartOptions()}
          style={{ height: '500px', width: '100%' }}
          theme="light"
          notMerge={true}
          lazyUpdate={true}
          opts={{ renderer: 'canvas' }}
        />
      </div>

      {/* Aggregate Statistics */}
      <div
        style={{
          background: '#fafafa',
          border: '1px solid #f0f0f0',
          padding: '20px',
          marginTop: '20px'
        }}
      >
        <h3 style={{ marginBottom: '15px', fontSize: '16px' }}>
          Aggregate Statistics
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
          <div>
            <div style={{ color: 'rgba(0, 0, 0, 0.65)', fontSize: '12px' }}>Total Repositories</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
              {data.aggregate.total_repos_evaluated}
            </div>
          </div>
          <div>
            <div style={{ color: 'rgba(0, 0, 0, 0.65)', fontSize: '12px' }}>Total Commits</div>
            <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
              {data.aggregate.total_commits}
            </div>
          </div>
          {Object.entries(data.aggregate.average_scores).map(([key, value], idx) => (
            <div key={key}>
              <div style={{ color: 'rgba(0, 0, 0, 0.65)', fontSize: '12px' }}>
                Avg {data.dimension_names[idx]?.split('&')[0]?.trim()}
              </div>
              <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                {value.toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Repository Details */}
      <div style={{ marginTop: '30px' }}>
        <h3 style={{ marginBottom: '15px', fontSize: '16px' }}>
          Repository Details
        </h3>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {data.comparisons.map((comp, idx) => (
            <div
              key={comp.repo}
              style={{
                background: '#ffffff',
                border: `1px solid ${colors[idx % colors.length]}`,
                padding: '15px'
              }}
            >
              <div style={{ marginBottom: '15px' }}>
                <span style={{ color: colors[idx % colors.length], fontSize: '16px', fontWeight: 'bold' }}>
                  {comp.repo}
                </span>
                <span style={{ color: 'rgba(0, 0, 0, 0.65)', marginLeft: '15px' }}>
                  Commits: {comp.total_commits} | {comp.cached ? 'Cached' : 'Fresh Analysis'}
                </span>
              </div>
              <Descriptions
                bordered
                column={{ xs: 1, sm: 1, md: 2, lg: 2, xl: 3, xxl: 3 }}
                size="small"
                style={{
                  background: 'transparent'
                }}
                labelStyle={{
                  color: 'rgba(0, 0, 0, 0.65)',
                  background: '#fafafa',
                  fontSize: '12px',
                  fontWeight: '500',
                  padding: '8px 12px'
                }}
                contentStyle={{
                  color: 'rgba(0, 0, 0, 0.85)',
                  background: '#ffffff',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  padding: '8px 12px'
                }}
              >
                {Object.entries(comp.scores).map(([key, value], dimIdx) => (
                  <Descriptions.Item
                    key={key}
                    label={data.dimension_names[dimIdx]}
                  >
                    {value.toFixed(0)}
                  </Descriptions.Item>
                ))}
              </Descriptions>
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
                <li key={idx} style={{ color: 'rgba(0, 0, 0, 0.65)' }}>
                  {failed.repo}: {failed.reason}
                </li>
              ))}
            </ul>
          }
          type="warning"
          showIcon
          style={{
            marginTop: '20px',
            borderRadius: 8
          }}
        />
      )}
    </Card>
  );
}
