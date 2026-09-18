import { readFile } from 'node:fs/promises';
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import { InternkimConnection, type ConnectionSettings } from './connection';
import { registerToolDiscovery } from './tools';

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function settingsFromManifests(plugin: unknown, manifest: unknown): ConnectionSettings {
  if (!isRecord(plugin) || typeof plugin.version !== 'string') {
    throw new Error('InternKim plugin manifest must declare its version');
  }
  const servers = isRecord(manifest) ? manifest.mcpServers : undefined;
  const server = isRecord(servers) ? servers.internkim : undefined;
  if (!isRecord(server) || server.type !== 'streamable-http' || typeof server.url !== 'string') {
    throw new Error('InternKim MCP manifest must declare a Streamable HTTP server');
  }
  return { serverURL: new URL(server.url), version: plugin.version };
}

export default async function internkimPlugin(pi: ExtensionAPI): Promise<void> {
  const plugin: unknown = JSON.parse(await readFile(new URL('../../plugin.json', import.meta.url), 'utf8'));
  const manifest: unknown = JSON.parse(await readFile(new URL('../../mcp.json', import.meta.url), 'utf8'));
  const settings = settingsFromManifests(plugin, manifest);
  const connection = new InternkimConnection({
    ...settings,
    serverURL: process.env.INTERNKIM_MCP_URL ? new URL(process.env.INTERNKIM_MCP_URL) : settings.serverURL,
    bearerToken: process.env.INTERNKIM_MCP_BEARER_TOKEN
  });
  registerToolDiscovery(pi, connection);
  pi.on('session_shutdown', async () => connection.close());
}
