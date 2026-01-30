'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, Table, Select, Button, Tag, message } from 'antd';
import type { TableColumnsType } from 'antd';
import { GithubOutlined } from '@ant-design/icons';
import { validationApi } from '../../utils/validationApi';
import { TestRepository, DatasetStats } from './types';
import { useI18n } from '../I18nContext';

interface DatasetOverviewProps {
  onViewEvaluation?: (repo: TestRepository) => void;
}

export default function DatasetOverview({ onViewEvaluation }: DatasetOverviewProps) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [repos, setRepos] = useState<TestRepository[]>([]);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [total, setTotal] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>(undefined);

  const loadStats = useCallback(async () => {
    try {
      const result = await validationApi.getDatasetInfo();
      if (result.success) {
        const totalRepos = result.total_repos;
        const allRepos = result.repos || [];

        const categories = new Set(allRepos.map((r: any) => r.category)).size;
        const platforms = new Set(allRepos.map((r: any) => r.platform)).size;
        const groundTruth = allRepos.filter((r: any) => r.is_ground_truth).length;
        const edgeCases = allRepos.filter((r: any) => r.is_edge_case).length;

        const skillCounts = {
          novice: allRepos.filter((r: any) => r.skill_level === 'novice').length,
          intermediate: allRepos.filter((r: any) => r.skill_level === 'intermediate').length,
          senior: allRepos.filter((r: any) => r.skill_level === 'senior').length,
          architect: allRepos.filter((r: any) => r.skill_level === 'architect').length,
          expert: allRepos.filter((r: any) => r.skill_level === 'expert').length,
        };

        setStats({
          total: totalRepos,
          ground_truth: groundTruth,
          edge_cases: edgeCases,
          categories,
          platforms,
          ...skillCounts,
        });
      }
    } catch (err) {
      message.error(t('validation.dataset.load_stats_error'));
      console.error('Failed to load dataset stats:', err);
    }
  }, [t]);

  const loadRepos = useCallback(
    async (currentPage: number, category?: string) => {
      setLoading(true);
      try {
        const result = await validationApi.getRepos({
          page: currentPage,
          per_page: perPage,
          category,
        });
        if (result.success) {
          setRepos(result.repos);
          setTotal(result.total);
        }
      } catch (err) {
        message.error(t('validation.dataset.load_repos_error'));
        console.error('Failed to load repos:', err);
      } finally {
        setLoading(false);
      }
    },
    [perPage, t]
  );

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadRepos(page, selectedCategory);
  }, [page, selectedCategory, loadRepos]);

  const columns: TableColumnsType<TestRepository> = [
    {
      title: t('validation.dataset.table.platform'),
      dataIndex: 'platform',
      key: 'platform',
      width: 100,
      render: (platform: string) => (
        <Tag color={platform === 'github' ? 'blue' : 'orange'}>{platform.toUpperCase()}</Tag>
      ),
    },
    {
      title: t('validation.dataset.table.repo'),
      key: 'repo',
      render: (_, record) => (
        <div>
          <div>
            <strong>
              {record.owner}/{record.repo}
            </strong>
          </div>
          <div style={{ fontSize: 12, color: '#666' }}>{record.description}</div>
        </div>
      ),
    },
    {
      title: t('validation.dataset.table.author'),
      dataIndex: 'author',
      key: 'author',
      width: 150,
    },
    {
      title: t('validation.dataset.table.category'),
      dataIndex: 'category',
      key: 'category',
      width: 150,
      render: (category: string) => <Tag>{category}</Tag>,
    },
    {
      title: t('validation.dataset.table.skill_level'),
      dataIndex: 'skill_level',
      key: 'skill_level',
      width: 120,
      render: (level: string | null) => {
        if (!level) return <Tag>N/A</Tag>;
        const colorMap: Record<string, string> = {
          expert: 'purple',
          architect: 'blue',
          senior: 'cyan',
          intermediate: 'green',
          novice: 'default',
        };
        return <Tag color={colorMap[level] || 'default'}>{t(`validation.skill.${level}`)}</Tag>;
      },
    },
    {
      title: t('validation.dataset.table.actions'),
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<GithubOutlined />}
          onClick={() => onViewEvaluation?.(record)}
        >
          {t('validation.dataset.view_evaluation')}
        </Button>
      ),
    },
  ];

  return (
    <div>
      {stats && (
        <div style={{ marginBottom: 24 }}>
          <Row gutter={16}>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('validation.dataset.total_repos')}
                  value={stats.total}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('validation.dataset.categories')}
                  value={stats.categories}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('validation.dataset.ground_truth')}
                  value={stats.ground_truth}
                  valueStyle={{ color: '#cf1322' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={t('validation.dataset.expert')}
                  value={stats.expert}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Card>
            </Col>
          </Row>
        </div>
      )}

      <Card
        title={t('validation.dataset.repos_list')}
        extra={
          <Select
            style={{ width: 200 }}
            placeholder={t('validation.dataset.filter_category')}
            allowClear
            value={selectedCategory}
            onChange={(value) => {
              setSelectedCategory(value);
              setPage(1);
            }}
          >
            <Select.Option value="ground_truth">{t('validation.category.ground_truth')}</Select.Option>
            <Select.Option value="famous_developer">{t('validation.category.famous_developer')}</Select.Option>
            <Select.Option value="dimension_specialist">{t('validation.category.dimension_specialist')}</Select.Option>
            <Select.Option value="rising_star">{t('validation.category.rising_star')}</Select.Option>
            <Select.Option value="temporal_evolution">{t('validation.category.temporal_evolution')}</Select.Option>
            <Select.Option value="edge_case">{t('validation.category.edge_case')}</Select.Option>
            <Select.Option value="corporate_team">{t('validation.category.corporate_team')}</Select.Option>
            <Select.Option value="domain_specialist">{t('validation.category.domain_specialist')}</Select.Option>
            <Select.Option value="international">{t('validation.category.international')}</Select.Option>
            <Select.Option value="comparison_pair">{t('validation.category.comparison_pair')}</Select.Option>
          </Select>
        }
      >
        <Table
          columns={columns}
          dataSource={repos}
          loading={loading}
          rowKey={(record) => record.identifier}
          pagination={{
            current: page,
            pageSize: perPage,
            total,
            onChange: (newPage) => setPage(newPage),
            showSizeChanger: false,
            showTotal: (total, range) => `${range[0]}-${range[1]} of ${total}`,
          }}
        />
      </Card>
    </div>
  );
}
