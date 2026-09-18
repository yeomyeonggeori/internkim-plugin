import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { CallToolResultSchema, type CallToolResult, type Tool } from '@modelcontextprotocol/sdk/types.js';

export type ConnectionSettings = {
  serverURL: URL;
  bearerToken?: string;
  version: string;
};

export interface ToolConnection {
  listTools(signal?: AbortSignal): Promise<Tool[]>;
  callTool(name: string, argumentsValue: Record<string, unknown>, signal?: AbortSignal): Promise<CallToolResult>;
  close(): Promise<void>;
}

export class InternkimConnection implements ToolConnection {
  private connection: Promise<Client> | undefined;

  constructor(private readonly settings: ConnectionSettings) {}

  private async connect(): Promise<Client> {
    const client = new Client({ name: 'internkim-pi', version: this.settings.version });
    const headers = new Headers();
    if (this.settings.bearerToken) headers.set('Authorization', `Bearer ${this.settings.bearerToken}`);
    const transport = new StreamableHTTPClientTransport(this.settings.serverURL, {
      requestInit: { headers }
    });
    try {
      await client.connect(transport);
    } catch (error) {
      await transport.close();
      throw error;
    }
    return client;
  }

  private getClient(): Promise<Client> {
    this.connection ??= this.connect().catch((error: unknown) => {
      this.connection = undefined;
      throw error;
    });
    return this.connection;
  }

  async listTools(signal?: AbortSignal): Promise<Tool[]> {
    signal?.throwIfAborted();
    const client = await this.getClient();
    const tools: Tool[] = [];
    const seenCursors = new Set<string>();
    let cursor: string | undefined;
    do {
      const page = await client.listTools({ cursor }, { signal });
      tools.push(...page.tools);
      cursor = page.nextCursor;
      if (cursor && seenCursors.has(cursor)) throw new Error('InternKim MCP repeated a tool catalog cursor');
      if (cursor) seenCursors.add(cursor);
    } while (cursor);
    return tools;
  }

  async callTool(name: string, argumentsValue: Record<string, unknown>, signal?: AbortSignal): Promise<CallToolResult> {
    signal?.throwIfAborted();
    const client = await this.getClient();
    const result = await client.callTool({ name, arguments: argumentsValue }, CallToolResultSchema, { signal });
    return CallToolResultSchema.parse(result);
  }

  async close(): Promise<void> {
    const connection = this.connection;
    this.connection = undefined;
    if (connection) await (await connection).close();
  }
}
