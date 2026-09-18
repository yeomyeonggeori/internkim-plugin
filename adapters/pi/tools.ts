import type { AgentToolResult, ExtensionAPI } from '@earendil-works/pi-coding-agent';
import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { Type } from 'typebox';
import type { ToolConnection } from './connection';
import { presentToolResult } from './results';

type ToolRegistry = Pick<ExtensionAPI, 'registerTool' | 'getAllTools' | 'getActiveTools' | 'setActiveTools'>;
type DiscoveryResult =
  | { missing: string[]; available: { name: string; description?: string }[] }
  | { loaded: string[] };

export function toolNameForPi(name: string): string {
  return `internkim__${name}`;
}

export function selectTools(tools: Tool[], names: string[]): { selected: Tool[]; missing: string[] } {
  const catalog = new Map<string, Tool>();
  for (const tool of tools) {
    if (catalog.has(tool.name)) throw new Error(`InternKim MCP duplicated tool ${tool.name}`);
    catalog.set(tool.name, tool);
  }
  const requested = [...new Set(names)];
  return {
    selected: requested.flatMap((name) => {
      const tool = catalog.get(name);
      return tool ? [tool] : [];
    }),
    missing: requested.filter((name) => !catalog.has(name))
  };
}

function registerBusinessTool(registry: ToolRegistry, connection: ToolConnection, tool: Tool): void {
  registry.registerTool({
    name: toolNameForPi(tool.name),
    label: `InternKim: ${tool.name}`,
    description: tool.description ?? tool.name,
    parameters: Type.Unsafe<Record<string, unknown>>(tool.inputSchema),
    async execute(_toolCallID, input, signal) {
      return presentToolResult(await connection.callTool(tool.name, input, signal));
    }
  });
}

export function registerToolDiscovery(registry: ToolRegistry, connection: ToolConnection): void {
  const ownedNames = new Set<string>();
  registry.registerTool({
    name: 'internkim_tools',
    label: 'InternKim tools',
    description: 'Load InternKim tools by their exact canonical names before calling them. Use names=[] to list available names and descriptions. Loaded tools use the internkim__ prefix and their server-provided schemas.',
    parameters: Type.Object({ names: Type.Array(Type.String()) }, { additionalProperties: false }),
    async execute(_toolCallID, input, signal): Promise<AgentToolResult<DiscoveryResult>> {
      const tools = await connection.listTools(signal);
      const selection = selectTools(tools, input.names);
      if (input.names.length === 0 || selection.missing.length > 0) {
        const details = {
          missing: selection.missing,
          available: tools.map(({ name, description }) => ({ name, description }))
        };
        return { content: [{ type: 'text', text: JSON.stringify(details) }], details };
      }
      installTools(registry, connection, selection.selected, ownedNames);
      const details = { loaded: selection.selected.map((tool) => toolNameForPi(tool.name)) };
      return { content: [{ type: 'text', text: JSON.stringify(details) }], details };
    }
  });
}

function installTools(
  registry: ToolRegistry,
  connection: ToolConnection,
  tools: Tool[],
  ownedNames: Set<string>
): void {
  const occupiedNames = new Set(registry.getAllTools().map(({ name }) => name));
  for (const tool of tools) {
    const name = toolNameForPi(tool.name);
    if (occupiedNames.has(name) && !ownedNames.has(name)) {
      throw new Error(`InternKim tool ${name} conflicts with another registered tool`);
    }
  }
  for (const tool of tools) {
    registerBusinessTool(registry, connection, tool);
    ownedNames.add(toolNameForPi(tool.name));
  }
  registry.setActiveTools([...new Set([...registry.getActiveTools(), ...tools.map((tool) => toolNameForPi(tool.name))])]);
}
