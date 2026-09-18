import type { AgentToolResult } from '@earendil-works/pi-coding-agent';
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';

export function presentToolResult(result: CallToolResult): AgentToolResult<CallToolResult> {
  if (result.isError) throw new Error(JSON.stringify(result));
  const content: AgentToolResult<CallToolResult>['content'] = result.content.map((item) => {
    if (item.type === 'text') return { type: 'text', text: item.text };
    if (item.type === 'image') return { type: 'image', data: item.data, mimeType: item.mimeType };
    return { type: 'text', text: JSON.stringify(item) };
  });
  const structuredText = JSON.stringify(result.structuredContent);
  const hasStructuredText = content.some((item) => item.type === 'text' && item.text === structuredText);
  if (result.structuredContent !== undefined && !hasStructuredText) {
    content.push({ type: 'text', text: JSON.stringify({ structuredContent: result.structuredContent }) });
  }
  return { content, details: result };
}
