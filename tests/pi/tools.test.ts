import { describe, expect, test } from 'bun:test';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { registerToolDiscovery, selectTools, toolNameForPi } from '../../adapters/pi/tools';

const sampleTool: Tool = {
  name: 'sample_lookup',
  description: 'Read a sample record',
  inputSchema: {
    type: 'object',
    properties: { recordID: { type: 'string' } },
    required: ['recordID'],
    additionalProperties: false
  }
};

describe('Pi tool discovery', () => {
  test('selects exact identifiers without rewriting the schema', () => {
    const selected = selectTools([sampleTool], ['sample_lookup', 'sample_lookup']);
    expect(selected.selected).toEqual([sampleTool]);
    expect(selected.selected[0]).toBe(sampleTool);
    expect(selected.missing).toEqual([]);
    expect(selectTools([sampleTool], ['sample']).missing).toEqual(['sample']);
  });

  test('refuses duplicate server identities', () => {
    expect(() => selectTools([sampleTool, sampleTool], ['sample_lookup'])).toThrow('duplicated');
  });

  test('starts with discovery alone and does not connect at registration', () => {
    const registered: string[] = [];
    registerToolDiscovery({
      registerTool(tool) { registered.push(tool.name); },
      getAllTools() { return []; },
      getActiveTools() { return []; },
      setActiveTools() {}
    }, {
      async listTools() { throw new Error('registration must not connect'); },
      async callTool() { throw new Error('registration must not invoke'); },
      async close() {}
    });
    expect(registered).toEqual(['internkim_tools']);
    expect(toolNameForPi('sample_lookup')).toBe('internkim__sample_lookup');
  });
});
