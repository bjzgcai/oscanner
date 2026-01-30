'use client';

import { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Space, message, Modal } from 'antd';
import { useUserSettings } from './UserSettingsContext';
import { useI18n } from './I18nContext';

const { TextArea } = Input;

export default function Settings() {
  const [form] = Form.useForm();
  const userSettings = useUserSettings();
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);

  // Load initial values from context
  useEffect(() => {
    form.setFieldsValue({
      defaultUsername: userSettings.defaultUsername,
      repoUrls: userSettings.repoUrls.join('\n'),
      usernameGroups: userSettings.usernameGroups,
    });
  }, [userSettings, form]);

  // URL validation helper
  const parseRepoUrl = (input: string): boolean => {
    const trimmed = input.trim();
    if (!trimmed) return false;

    const githubPatterns = [
      /^https?:\/\/(?:www\.)?github\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^github\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^git@github\.com:([^\/]+)\/([^\/\s]+)\.git$/i,
      /^git@github\.com:([^\/]+)\/([^\/\s]+)$/i,
    ];
    for (const pattern of githubPatterns) {
      if (trimmed.match(pattern)) return true;
    }

    const giteePatterns = [
      /^https?:\/\/(?:www\.)?gitee\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^gitee\.com\/([^\/]+)\/([^\/\s]+)/i,
      /^git@gitee\.com:([^\/]+)\/([^\/\s]+)\.git$/i,
      /^git@gitee\.com:([^\/]+)\/([^\/\s]+)$/i,
    ];
    for (const pattern of giteePatterns) {
      if (trimmed.match(pattern)) return true;
    }

    return false;
  };

  const handleSave = async (values: { defaultUsername: string; repoUrls: string; usernameGroups: string }) => {
    setLoading(true);
    try {
      // Parse and validate URLs
      const urlLines = values.repoUrls
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0);

      // Validate max URLs
      if (urlLines.length > 5) {
        message.error(t('settings.validation.max_urls'));
        setLoading(false);
        return;
      }

      // Validate each URL
      for (const url of urlLines) {
        if (!parseRepoUrl(url)) {
          message.error(t('settings.validation.invalid_url', { url }));
          setLoading(false);
          return;
        }
      }

      // Update context (which also updates localStorage)
      userSettings.setDefaultUsername(values.defaultUsername.trim());
      userSettings.setRepoUrls(urlLines);
      userSettings.setUsernameGroups(values.usernameGroups.trim());

      message.success(t('settings.save_success'));
    } catch (error) {
      message.error(t('settings.save_error'));
      console.error('Failed to save settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    Modal.confirm({
      title: t('settings.reset_confirm'),
      onOk: () => {
        // Reset to defaults
        userSettings.setDefaultUsername('CarterWu');
        userSettings.setRepoUrls(['https://gitee.com/zgcai/oscanner']);
        userSettings.setUsernameGroups('');

        // Update form
        form.setFieldsValue({
          defaultUsername: 'CarterWu',
          repoUrls: 'https://gitee.com/zgcai/oscanner',
          usernameGroups: '',
        });

        message.success(t('settings.save_success'));
      },
    });
  };

  return (
    <div style={{ maxWidth: '900px', margin: '24px auto', padding: '0 24px' }}>
      <Card
        title={t('settings.title')}
        style={{ boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)' }}
      >
        <p style={{ marginBottom: '24px', color: '#6B7280' }}>{t('settings.description')}</p>

        <Form form={form} onFinish={handleSave} layout="vertical" size="large">
          <Form.Item
            name="defaultUsername"
            label={t('settings.default_username.label')}
            help={t('settings.default_username.help')}
            rules={[{ required: true, message: 'Please enter a username' }]}
          >
            <Input placeholder={t('settings.default_username.placeholder')} />
          </Form.Item>

          <Form.Item
            name="repoUrls"
            label={t('settings.repo_urls.label')}
            help={t('settings.repo_urls.help')}
            rules={[{ required: true, message: 'Please enter at least one repository URL' }]}
          >
            <TextArea
              rows={5}
              placeholder={t('settings.repo_urls.placeholder')}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          <Form.Item
            name="usernameGroups"
            label={t('settings.username_groups.label')}
            help={t('settings.username_groups.help')}
          >
            <TextArea
              rows={3}
              placeholder={t('settings.username_groups.placeholder')}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                {t('settings.save')}
              </Button>
              <Button onClick={handleReset} disabled={loading}>
                {t('settings.reset')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
