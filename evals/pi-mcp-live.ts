import { mkdir, mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  createAgentSession,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager
} from '@earendil-works/pi-coding-agent';
import { InMemoryCredentialStore } from '@earendil-works/pi-ai';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type Tool
} from '@modelcontextprotocol/sdk/types.js';

const projectID = 'eval-project-42';
const maximumToolCalls = 8;
const timeoutMilliseconds = 60_000;
type FixtureStatus = 'ready' | 'degraded' | 'paused';
const fixtureStatuses: FixtureStatus[] = ['ready', 'degraded', 'paused'];

type Arguments = {
  evidenceDirectory: string;
};

type ToolEvidence = {
  projectID: string;
  status: string;
  timestamp: string;
};

type TranscriptEntry = {
  type: string;
  toolName?: string;
  assistantEvent?: string;
};

type PiSession = Awaited<ReturnType<typeof createAgentSession>>['session'];

type Evidence = {
  model: string;
  startedAt: string;
  finishedAt: string;
  timedOut: boolean;
  limitReached: boolean;
  errorMessage?: string;
  transcript: TranscriptEntry[];
  messages: PiSession['messages'];
  toolCalls: ToolEvidence[];
  usage: ReturnType<PiSession['getSessionStats']>;
};

const tools: Tool[] = [
  {
    name: 'sample_project_lookup',
    description: 'Look up the status of one sample project.',
    inputSchema: {
      type: 'object',
      properties: { projectID: { type: 'string', description: 'The exact project identifier.' } },
      required: ['projectID'],
      additionalProperties: false
    }
  }
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function parseArguments(argumentList: readonly string[]): Arguments {
  const evidenceIndex = argumentList.indexOf('--evidence-dir');
  if (evidenceIndex < 0 || !argumentList[evidenceIndex + 1]) {
    throw new Error('Usage: bun evals/pi-mcp-live.ts --evidence-dir <directory>');
  }
  if (argumentList.length !== evidenceIndex + 2) throw new Error('Unknown evaluation argument');
  return { evidenceDirectory: resolve(argumentList[evidenceIndex + 1]) };
}

function fixtureStatus(): string {
  const index = crypto.getRandomValues(new Uint32Array(1))[0] % fixtureStatuses.length;
  return fixtureStatuses[index];
}

function hasExactProjectArguments(value: unknown): value is { projectID: string } {
  return isRecord(value) && Object.keys(value).length === 1 && value.projectID === projectID;
}

async function createFixtureServer(toolCalls: ToolEvidence[]): Promise<{
  url: URL;
  close: () => Promise<void>;
}> {
  const server = new Server({ name: 'pi-eval-fixture', version: '1' }, { capabilities: { tools: {} } });
  server.setRequestHandler(ListToolsRequestSchema, () => ({ tools }));
  server.setRequestHandler(CallToolRequestSchema, (request) => {
    if (request.params.name !== 'sample_project_lookup') {
      return { content: [{ type: 'text', text: 'unknown evaluation tool' }], isError: true };
    }
    if (!hasExactProjectArguments(request.params.arguments)) {
      return { content: [{ type: 'text', text: 'invalid fixture arguments' }], isError: true };
    }
    const requestedProjectID = request.params.arguments.projectID;
    const status = fixtureStatus();
    toolCalls.push({ projectID: requestedProjectID, status, timestamp: new Date().toISOString() });
    return { content: [{ type: 'text', text: JSON.stringify({ projectID: requestedProjectID, status }) }] };
  });
  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: () => crypto.randomUUID(),
    enableJsonResponse: true
  });
  await server.connect(transport);
  const httpServer = Bun.serve({
    hostname: '127.0.0.1',
    port: 0,
    fetch: (request) => transport.handleRequest(request)
  });
  return {
    url: new URL(`http://127.0.0.1:${httpServer.port}`),
    close: async () => {
      await transport.close();
      await server.close();
      httpServer.stop(true);
    }
  };
}

function transcriptEntry(event: { type: string; toolName?: string; assistantMessageEvent?: { type: string } }): TranscriptEntry {
  if (event.type === 'tool_execution_start' || event.type === 'tool_execution_end') {
    return { type: event.type, toolName: event.toolName };
  }
  if (event.type === 'message_update') return { type: event.type, assistantEvent: event.assistantMessageEvent?.type };
  return { type: event.type };
}

async function runEvaluation(modelID: string, evidenceDirectory: string): Promise<void> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) throw new Error('OPENROUTER_API_KEY is required for the live Pi evaluation');
  const temporaryDirectory = await mkdtemp(join(tmpdir(), 'internkim-pi-eval-'));
  const agentDirectory = join(temporaryDirectory, 'agent');
  const workingDirectory = join(temporaryDirectory, 'cwd');
  await mkdir(workingDirectory, { recursive: true });
  await mkdir(evidenceDirectory, { recursive: true });
  const toolCalls: ToolEvidence[] = [];
  const fixture = await createFixtureServer(toolCalls);
  const previousURL = process.env.INTERNKIM_MCP_URL;
  const previousBearerToken = process.env.INTERNKIM_MCP_BEARER_TOKEN;
  process.env.INTERNKIM_MCP_URL = fixture.url.toString();
  delete process.env.INTERNKIM_MCP_BEARER_TOKEN;
  const startedAt = new Date().toISOString();
  const transcript: TranscriptEntry[] = [];
  let timedOut = false;
  let limitReached = false;
  let errorMessage: string | undefined;
  let toolExecutionCount = 0;
  let session: Awaited<ReturnType<typeof createAgentSession>>['session'] | undefined;
  try {
    const modelRuntime = await ModelRuntime.create({
      credentials: new InMemoryCredentialStore(),
      modelsPath: null,
      modelsStorePath: join(agentDirectory, 'models.json'),
      allowModelNetwork: false
    });
    await modelRuntime.setRuntimeApiKey('openrouter', apiKey);
    const model = modelRuntime.getModel('openrouter', modelID);
    if (!model) throw new Error(`PI_EVAL_MODEL was not found in the OpenRouter model catalog: ${modelID}`);
    const resourceLoader = new DefaultResourceLoader({
      cwd: workingDirectory,
      agentDir: agentDirectory,
      additionalExtensionPaths: [fileURLToPath(new URL('../adapters/pi/index.ts', import.meta.url))]
    });
    await resourceLoader.reload();
    const created = await createAgentSession({
      cwd: workingDirectory,
      agentDir: agentDirectory,
      modelRuntime,
      model,
      noTools: 'builtin',
      resourceLoader,
      sessionManager: SessionManager.inMemory(workingDirectory)
    });
    session = created.session;
    session.subscribe((event) => {
      transcript.push(transcriptEntry(event));
      if (event.type !== 'tool_execution_start') return;
      toolExecutionCount += 1;
      if (toolExecutionCount < maximumToolCalls) return;
      limitReached = true;
      void session?.abort();
    });
    const timeout = setTimeout(() => {
      timedOut = true;
      void session?.abort();
    }, timeoutMilliseconds);
    try {
      await session.prompt(`Discover the available InternKim tools and find the status of project ${projectID}. Do not guess a tool name. Use the discovered tool with the exact project identifier, then report the returned status.`);
    } catch (error: unknown) {
      errorMessage = error instanceof Error ? error.message : 'Pi session failed with an unknown error';
    } finally {
      clearTimeout(timeout);
    }
    const evidence: Evidence = {
      model: modelID,
      startedAt,
      finishedAt: new Date().toISOString(),
      timedOut,
      limitReached,
      ...(errorMessage ? { errorMessage } : {}),
      transcript,
      messages: session.messages,
      toolCalls: [...toolCalls],
      usage: session.getSessionStats()
    };
    const evidenceDocument = JSON.stringify(evidence, null, 2).replaceAll(apiKey, '[redacted]');
    await writeFile(join(evidenceDirectory, 'pi-mcp-live.json'), evidenceDocument);
    if (timedOut) throw new Error(`Pi evaluation timed out after ${timeoutMilliseconds}ms`);
    if (limitReached) throw new Error(`Pi evaluation reached the ${maximumToolCalls}-tool limit`);
    if (toolCalls.length === 0) throw new Error('Pi evaluation did not complete an exact sample project lookup');
    if (errorMessage) throw new Error(errorMessage);
  } finally {
    session?.dispose();
    if (previousURL === undefined) delete process.env.INTERNKIM_MCP_URL;
    else process.env.INTERNKIM_MCP_URL = previousURL;
    if (previousBearerToken === undefined) delete process.env.INTERNKIM_MCP_BEARER_TOKEN;
    else process.env.INTERNKIM_MCP_BEARER_TOKEN = previousBearerToken;
    await fixture.close();
    await rm(temporaryDirectory, { recursive: true, force: true });
  }
}

async function main(): Promise<void> {
  const modelID = process.env.PI_EVAL_MODEL;
  if (!modelID) throw new Error('PI_EVAL_MODEL is required; choose the OpenRouter model explicitly');
  const argumentsValue = parseArguments(process.argv.slice(2));
  await runEvaluation(modelID, argumentsValue.evidenceDirectory);
}

if (import.meta.main) {
  await main();
}
