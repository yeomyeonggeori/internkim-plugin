import { afterEach, describe, expect, test } from 'bun:test';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type Tool
} from '@modelcontextprotocol/sdk/types.js';
import { InternkimConnection } from '../../adapters/pi/connection';

type FixtureOptions = {
  bearerToken?: string;
  pauseInvocation?: boolean;
  invocationStatus?: number;
  repeatedToolCursor?: boolean;
  invocationResult?: {
    content: [{ type: 'text'; text: string }];
    structuredContent: { value: string };
    isError: true;
  };
};

type Fixture = {
  connection: InternkimConnection;
  calls: () => number;
  invocationAttempts: () => number;
  waitForInvocation: () => Promise<void>;
  releaseInvocation: () => void;
  requests: () => number;
  methods: () => string[];
  authorizationHeaders: () => string[];
  close: () => Promise<void>;
};

const tools: Tool[] = [
  {
    name: 'sample_lookup',
    description: 'Look up a sample value.',
    inputSchema: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] }
  },
  {
    name: 'sample_record',
    description: 'Record a sample value.',
    inputSchema: { type: 'object', properties: { value: { type: 'string' } }, required: ['value'] }
  }
];

const fixtures: Fixture[] = [];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

async function createFixture(options: FixtureOptions = {}): Promise<Fixture> {
  let requestCount = 0;
  let callCount = 0;
  let invocationAttemptCount = 0;
  let resolveInvocationStarted!: () => void;
  let resolveInvocationRelease!: () => void;
  const invocationStarted = new Promise<void>((resolve) => {
    resolveInvocationStarted = resolve;
  });
  const invocationRelease = new Promise<void>((resolve) => {
    resolveInvocationRelease = resolve;
  });
  const requestMethods: string[] = [];
  const authorizationHeaders: string[] = [];
  const server = new Server({ name: 'fixture', version: '1' }, { capabilities: { tools: {} } });
  server.setRequestHandler(ListToolsRequestSchema, (request) => {
    const cursor = request.params?.cursor;
    if (cursor) return { tools: [tools[1]], ...(options.repeatedToolCursor ? { nextCursor: cursor } : {}) };
    return { tools: [tools[0]], nextCursor: 'page-2' };
  });
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    callCount += 1;
    if (options.pauseInvocation) {
      resolveInvocationStarted();
      await invocationRelease;
    }
    return options.invocationResult ?? {
      content: [{ type: 'text', text: JSON.stringify(request.params.arguments ?? {}) }]
    };
  });
  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: () => crypto.randomUUID(),
    enableJsonResponse: true
  });
  await server.connect(transport);
  const httpServer = Bun.serve({
    hostname: '127.0.0.1',
    port: 0,
    fetch: async (request) => {
      requestCount += 1;
      requestMethods.push(request.method);
      authorizationHeaders.push(request.headers.get('authorization') ?? '');
      const body = await request.clone().text();
      const parsedBody: unknown = JSON.parse(body || 'null');
      const isToolInvocation = isRecord(parsedBody) && parsedBody.method === 'tools/call';
      if (isToolInvocation) invocationAttemptCount += 1;
      if (options.invocationStatus && isToolInvocation) {
        return new Response('fixture failure', { status: options.invocationStatus });
      }
      return transport.handleRequest(request);
    }
  });
  const connection = new InternkimConnection({
    serverURL: new URL(`http://127.0.0.1:${httpServer.port}`),
    bearerToken: options.bearerToken,
    version: 'fixture'
  });
  const fixture: Fixture = {
    connection,
    calls: () => callCount,
    invocationAttempts: () => invocationAttemptCount,
    waitForInvocation: () => invocationStarted,
    releaseInvocation: resolveInvocationRelease,
    requests: () => requestCount,
    methods: () => requestMethods,
    authorizationHeaders: () => authorizationHeaders,
    close: async () => {
      await connection.close();
      await transport.close();
      await server.close();
      httpServer.stop(true);
    }
  };
  fixtures.push(fixture);
  return fixture;
}

afterEach(async () => {
  while (fixtures.length > 0) await fixtures.pop()?.close();
});

describe('InternKim MCP connection', () => {
  test('connects lazily, forwards bearer credentials, paginates, and preserves schemas', async () => {
    const fixture = await createFixture({ bearerToken: 'ik_fixture' });

    expect(fixture.requests()).toBe(0);
    const listedTools = await fixture.connection.listTools();

    expect(listedTools).toEqual(tools);
    expect(fixture.requests()).toBeGreaterThan(0);
    expect(fixture.methods()).toContain('POST');
    expect(fixture.authorizationHeaders().every((header) => header === 'Bearer ik_fixture')).toBe(true);
  });

  test('preserves structured content and an error result from one invocation', async () => {
    const fixture = await createFixture({
      invocationResult: {
        content: [{ type: 'text', text: 'rejected' }],
        structuredContent: { value: 'raw' },
        isError: true
      }
    });

    const result = await fixture.connection.callTool('sample_lookup', { query: 'fixture' });

    expect(result).toEqual({
      content: [{ type: 'text', text: 'rejected' }],
      structuredContent: { value: 'raw' },
      isError: true
    });
    expect(fixture.calls()).toBe(1);
  });

  for (const status of [401, 500]) {
    test(`does not retry an invocation after HTTP ${status}`, async () => {
      const fixture = await createFixture({ invocationStatus: status });

      await expect(fixture.connection.callTool('sample_lookup', {})).rejects.toThrow();

      expect(fixture.calls()).toBe(0);
      expect(fixture.invocationAttempts()).toBe(1);
    });
  }

  test('fails closed when the tool catalog repeats a cursor', async () => {
    const fixture = await createFixture({ repeatedToolCursor: true });

    await expect(fixture.connection.listTools()).rejects.toThrow('repeated a tool catalog cursor');
  });

  test('does not send an invocation after its signal is aborted', async () => {
    const fixture = await createFixture();
    const controller = new AbortController();
    controller.abort();

    await expect(fixture.connection.callTool('sample_lookup', {}, controller.signal)).rejects.toThrow();

    expect(fixture.calls()).toBe(0);
    expect(fixture.requests()).toBe(0);
  });

  test('cancels an invocation already in flight', async () => {
    const fixture = await createFixture({ pauseInvocation: true });
    const controller = new AbortController();
    const invocation = fixture.connection.callTool('sample_lookup', {}, controller.signal);

    await fixture.waitForInvocation();
    controller.abort();
    await expect(invocation).rejects.toThrow();

    fixture.releaseInvocation();
    expect(fixture.invocationAttempts()).toBe(1);
  });
});
