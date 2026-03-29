import { environment } from '../../environments/environment';

export interface RuntimeConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
}

declare global {
  interface Window {
    __stockRadarConfig?: Partial<RuntimeConfig>;
  }
}

function stripTrailingSlash(value: string): string {
  return value.endsWith('/') ? value.slice(0, -1) : value;
}

function deriveWsBaseUrl(apiBaseUrl: string): string {
  if (apiBaseUrl.startsWith('https://')) {
    return `wss://${apiBaseUrl.slice('https://'.length)}`;
  }
  if (apiBaseUrl.startsWith('http://')) {
    return `ws://${apiBaseUrl.slice('http://'.length)}`;
  }
  if (apiBaseUrl.startsWith('/')) {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${location.host}${apiBaseUrl}`;
  }
  return apiBaseUrl;
}

function normalizeWsBaseUrl(rawWsBaseUrl: string | undefined, apiBaseUrl: string): string {
  if (!rawWsBaseUrl) {
    return deriveWsBaseUrl(apiBaseUrl);
  }

  const trimmed = stripTrailingSlash(rawWsBaseUrl);
  if (trimmed.startsWith('ws://') || trimmed.startsWith('wss://')) {
    return trimmed;
  }
  return deriveWsBaseUrl(trimmed);
}

const rawConfig = window.__stockRadarConfig ?? {};
const apiBaseUrl = stripTrailingSlash(rawConfig.apiBaseUrl ?? environment.apiBaseUrl);

export const runtimeConfig: RuntimeConfig = {
  apiBaseUrl,
  wsBaseUrl: normalizeWsBaseUrl(rawConfig.wsBaseUrl, apiBaseUrl),
};
