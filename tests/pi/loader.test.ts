import { expect, test } from 'bun:test';
import { discoverAndLoadExtensions } from '@earendil-works/pi-coding-agent';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('the native Pi loader loads discovery without connecting or changing user settings', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'internkim-pi-loader-'));
  try {
    const extensionPath = new URL('../../adapters/pi/index.ts', import.meta.url).pathname;
    const result = await discoverAndLoadExtensions([extensionPath], directory, directory);
    expect(result.errors).toEqual([]);
    expect(result.extensions).toHaveLength(1);
    expect([...result.extensions[0].tools.keys()]).toEqual(['internkim_tools']);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
