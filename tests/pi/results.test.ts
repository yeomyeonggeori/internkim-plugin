import { describe, expect, test } from 'bun:test';
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';
import { presentToolResult } from '../../adapters/pi/results';

describe('MCP results in Pi', () => {
  test('preserves text, images, structured effects, and raw details', () => {
    const result: CallToolResult = {
      content: [
        { type: 'text', text: 'recorded' },
        { type: 'image', data: 'aW1hZ2U=', mimeType: 'image/png' }
      ],
      structuredContent: { effects: [{ recordID: 'sample-record', action: 'created' }] }
    };
    const presented = presentToolResult(result);
    expect(presented.details).toBe(result);
    expect(presented.content.slice(0, 2)).toEqual([
      { type: 'text', text: 'recorded' },
      { type: 'image', data: 'aW1hZ2U=', mimeType: 'image/png' }
    ]);
    expect(presented.content[2]).toEqual({
      type: 'text',
      text: JSON.stringify({ structuredContent: result.structuredContent })
    });
  });

  test('keeps resource references without fetching their contents', () => {
    const result: CallToolResult = {
      content: [{ type: 'resource_link', uri: 'https://example.test/report', name: 'report' }]
    };
    expect(presentToolResult(result).content).toEqual([
      { type: 'text', text: JSON.stringify(result.content[0]) }
    ]);
  });

  test('does not repeat structured output already present as identical JSON text', () => {
    const structuredContent = { operationID: 'sample-operation', state: 'completed' };
    const result: CallToolResult = {
      content: [{ type: 'text', text: JSON.stringify(structuredContent) }],
      structuredContent
    };
    const presented = presentToolResult(result);
    expect(presented.content).toHaveLength(1);
    expect(presented.details).toBe(result);
  });

  test('a refused call cannot be presented as successful', () => {
    const result: CallToolResult = {
      isError: true,
      content: [{ type: 'text', text: 'approval required' }],
      structuredContent: { operationID: 'sample-operation', state: 'waiting_approval' }
    };
    expect(() => presentToolResult(result)).toThrow(JSON.stringify(result));
  });
});
