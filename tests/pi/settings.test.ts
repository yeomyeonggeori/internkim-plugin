import { expect, test } from 'bun:test';
import { settingsFromManifests } from '../../adapters/pi/index';

test('the Pi adapter reads the same portable server and plugin version', () => {
  const settings = settingsFromManifests({ version: '1.2.3' }, {
    mcpServers: { internkim: { type: 'streamable-http', url: 'https://example.test/mcp' } }
  });
  expect(settings.serverURL.href).toBe('https://example.test/mcp');
  expect(settings.version).toBe('1.2.3');
  expect(settings.bearerToken).toBeUndefined();
});

test('an unsupported source transport fails without being rewritten', () => {
  expect(() => settingsFromManifests({ version: '1.2.3' }, {
    mcpServers: { internkim: { type: 'stdio', command: 'sample' } }
  })).toThrow('Streamable HTTP');
});
