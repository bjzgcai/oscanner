'use client';

import { useState, useEffect, useCallback } from 'react';
import { Modal, Input, Radio, message } from 'antd';
import { useAppSettings } from './AppSettingsContext';
import { useI18n } from './I18nContext';
import { getApiBaseUrl } from '@/utils/apiBase';

const API_SERVER_URL = getApiBaseUrl();

export default function LlmConfigModal() {
  const { model, llmModalOpen, setLlmModalOpen } = useAppSettings();
  const { t } = useI18n();

  const [llmConfigPath, setLlmConfigPath] = useState<string>('');
  const [llmMode, setLlmMode] = useState<'openrouter' | 'openai'>('openrouter');
  const [openRouterKey, setOpenRouterKey] = useState('');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmBaseUrl, setLlmBaseUrl] = useState('');
  const [llmChatUrl, setLlmChatUrl] = useState('');
  const [llmFallbackModels, setLlmFallbackModels] = useState('');
  const [giteeToken, setGiteeToken] = useState('');
  const [giteeTokenMasked, setGiteeTokenMasked] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [githubTokenMasked, setGithubTokenMasked] = useState('');

  const refreshLlmConfig = useCallback(async () => {
    try {
      const resp = await fetch(`${API_SERVER_URL}/api/config/llm`);
      if (!resp.ok) return;
      const cfg = await resp.json();
      setLlmConfigPath(String(cfg.path || ''));
      const mode = String(cfg.mode || 'openrouter') as 'openrouter' | 'openai';
      setLlmMode(mode);
      // do not hydrate secrets into inputs; keep empty
      setOpenRouterKey('');
      setLlmApiKey('');
      setGiteeToken('');
      setGithubToken('');
      setLlmBaseUrl(String(cfg.base_url || ''));
      setLlmChatUrl(String(cfg.chat_url || ''));
      setLlmFallbackModels(String(cfg.fallback_models || ''));
      setGiteeTokenMasked(String(cfg.gitee_token_masked || ''));
      setGithubTokenMasked(String(cfg.github_token_masked || ''));
    } catch {
      // ignore
    }
  }, []);

  // Refresh LLM config when modal opens
  useEffect(() => {
    if (llmModalOpen) {
      refreshLlmConfig();
    }
  }, [llmModalOpen, refreshLlmConfig]);

  const saveLlmConfig = useCallback(async () => {
    try {
      const body: Record<string, unknown> =
        llmMode === 'openrouter'
          ? {
              mode: 'openrouter',
              open_router_key: openRouterKey || null,
              gitee_token: giteeToken || null,
              github_token: githubToken || null,
            }
          : {
              mode: 'openai',
              llm_api_key: llmApiKey || null,
              llm_base_url: llmBaseUrl || null,
              llm_chat_url: llmChatUrl || null,
              llm_fallback_models: llmFallbackModels || null,
              gitee_token: giteeToken || null,
              github_token: githubToken || null,
            };

      const resp = await fetch(`${API_SERVER_URL}/api/config/llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        const errorData = await resp.json();
        message.error(`Failed to save LLM settings: ${errorData.detail || resp.statusText}`);
        return;
      }

      const data = await resp.json();
      if (!data.success) {
        message.error(data.message || 'Failed to save LLM settings');
        return;
      }

      message.success(`LLM settings saved. Path: ${data.path}`);
      setLlmModalOpen(false);

      // clear sensitive inputs after save
      setOpenRouterKey('');
      setLlmApiKey('');
      setGiteeToken('');
      setGithubToken('');
      await refreshLlmConfig();
    } catch (e: unknown) {
      message.error(`LLM settings save failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  }, [giteeToken, githubToken, llmApiKey, llmBaseUrl, llmChatUrl, llmFallbackModels, llmMode, openRouterKey, refreshLlmConfig, setLlmModalOpen]);

  return (
    <Modal
      title={t('llm.modal.title')}
      open={llmModalOpen}
      onCancel={() => setLlmModalOpen(false)}
      onOk={saveLlmConfig}
      okText={t('common.save')}
      cancelText={t('common.cancel')}
    >
      <div style={{ marginBottom: 12, color: 'rgba(0,0,0,0.65)' }}>
        {t('llm.modal.path')} <code>{llmConfigPath || '(unknown)'}</code>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>{t('llm.gitee_token.title')}</div>
        <Input.Password value={giteeToken} onChange={(e) => setGiteeToken(e.target.value)} placeholder="Gitee access token" />
        <div style={{ marginTop: 6, color: 'rgba(0,0,0,0.65)' }}>
          {t('llm.current_set')} <code>{giteeTokenMasked || t('llm.not_set')}</code> {t('llm.leave_empty_no_change')}
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>{t('llm.github_token.title')}</div>
        <Input.Password value={githubToken} onChange={(e) => setGithubToken(e.target.value)} placeholder="GitHub personal access token" />
        <div style={{ marginTop: 6, color: 'rgba(0,0,0,0.65)' }}>
          {t('llm.current_set')} <code>{githubTokenMasked || t('llm.not_set')}</code> {t('llm.leave_empty_no_change')}
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <Radio.Group value={llmMode} onChange={(e) => setLlmMode(e.target.value)}>
          <Radio value="openrouter">{t('llm.openrouter')}</Radio>
          <Radio value="openai">{t('llm.openai_compat')}</Radio>
        </Radio.Group>
      </div>

      {llmMode === 'openrouter' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>OPEN_ROUTER_KEY</div>
            <Input.Password value={openRouterKey} onChange={(e) => setOpenRouterKey(e.target.value)} placeholder="sk-or-..." />
          </div>
          <div style={{ color: 'rgba(0,0,0,0.65)' }}>
            {t('llm.current_model')} <code>{model}</code>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_BASE_URL</div>
            <Input value={llmBaseUrl} onChange={(e) => setLlmBaseUrl(e.target.value)} placeholder="https://api.siliconflow.cn/v1" />
          </div>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_API_KEY</div>
            <Input.Password value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} placeholder="Bearer token" />
          </div>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_CHAT_COMPLETIONS_URL（可选）</div>
            <Input value={llmChatUrl} onChange={(e) => setLlmChatUrl(e.target.value)} placeholder="https://.../chat/completions" />
          </div>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>OSCANNER_LLM_FALLBACK_MODELS（可选）</div>
            <Input value={llmFallbackModels} onChange={(e) => setLlmFallbackModels(e.target.value)} placeholder="model1,model2" />
          </div>
          <div style={{ color: 'rgba(0,0,0,0.65)' }}>
            {t('llm.current_model')} <code>{model}</code>
          </div>
        </div>
      )}
    </Modal>
  );
}
