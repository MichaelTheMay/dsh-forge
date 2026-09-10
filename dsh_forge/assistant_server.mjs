#!/usr/bin/env node
// Self-contained, dependency-free MCP server copied into an Assistant cell.

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import crypto from 'node:crypto';

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`missing ${name}`);
  return process.argv[index + 1];
}

const catalogPath = path.resolve(argument('--catalog'));
const draftDir = path.resolve(argument('--draft-dir'));
const payload = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
if (!payload || typeof payload !== 'object' || !Array.isArray(payload.entries)) throw new Error('catalog snapshot is invalid');
const entries = payload.entries.filter(row => row && typeof row === 'object').slice(0, 2048);
const versions = (Array.isArray(payload.saved_versions) ? payload.saved_versions : []).filter(row => row && typeof row === 'object').slice(0, 128);
fs.mkdirSync(draftDir, { recursive: true, mode: 0o700 });

function result(value, isError = false) {
  return {
    content: [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    structuredContent: value,
    isError,
  };
}

const tools = [
  {
    name: 'catalog_search',
    description: 'Search offline DSH Forge package, plugin, and fork metadata. Evidence is not a verification claim.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {
      query: { type: 'string', maxLength: 500 },
      type: { enum: ['all', 'package', 'plugin', 'fork'] },
      limit: { type: 'integer', minimum: 1, maximum: 50 },
    } },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  {
    name: 'catalog_compare',
    description: 'Compare up to eight exact catalog identities, preserving compatibility and risk evidence.',
    inputSchema: { type: 'object', additionalProperties: false, required: ['ids'], properties: {
      ids: { type: 'array', minItems: 1, maxItems: 8, items: { type: 'string', maxLength: 240 } },
    } },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
  },
  {
    name: 'configuration_save_draft',
    description: 'Write an inert configuration draft inside the disposable Assistant workspace for later human review.',
    inputSchema: { type: 'object', additionalProperties: false, required: ['name', 'version_id', 'selections'], properties: {
      name: { type: 'string', minLength: 1, maxLength: 80 },
      description: { type: 'string', maxLength: 4000 },
      version_id: { type: 'string', pattern: '^version_[0-9a-f]{12}$' },
      selections: { type: 'array', minItems: 1, maxItems: 64, items: {
        type: 'object', additionalProperties: false, required: ['type', 'id'],
        properties: { type: { enum: ['package', 'plugin', 'fork'] }, id: { type: 'string', maxLength: 240 } },
      } },
    } },
    annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false },
  },
];

function saveDraft(values) {
  const name = String(values.name || '').trim();
  const description = String(values.description || '').trim();
  const versionId = String(values.version_id || '');
  if (name.length < 1 || name.length > 80 || description.length > 4000) throw new Error('draft name or description is invalid');
  if (!/^version_[a-f0-9]{12}$/.test(versionId) || !versions.some(item => String(item.id) === versionId)) throw new Error('choose a saved Harness version');
  if (!Array.isArray(values.selections) || values.selections.length < 1 || values.selections.length > 64) throw new Error('choose one to 64 catalog artifacts');
  const known = new Set(entries.map(item => `${item.type}\0${item.id}`));
  const seen = new Set();
  const selections = [];
  for (const item of values.selections) {
    if (!item || typeof item !== 'object') throw new Error('selection must be an object');
    const type = String(item.type || '');
    const id = String(item.id || '');
    const key = `${type}\0${id}`;
    if (!known.has(key)) throw new Error('draft references an unknown catalog artifact');
    if (!seen.has(key)) { selections.push({ type, id }); seen.add(key); }
  }
  const createdAt = Date.now();
  const id = 'config_' + crypto.createHash('sha256').update(JSON.stringify([name, versionId, selections, createdAt])).digest('hex').slice(0, 20);
  const draft = {
    schema: 'dsh-forge.configuration-draft/v1', id, name, description,
    version_id: versionId, selections, status: 'draft', source: 'forge-assistant',
    created_at: createdAt, execution_authorized: false,
  };
  const destination = path.join(draftDir, `${id}.json`);
  const temporary = path.join(draftDir, `.draft-${crypto.randomBytes(12).toString('hex')}.tmp`);
  const descriptor = fs.openSync(temporary, 'wx', 0o600);
  try { fs.writeFileSync(descriptor, JSON.stringify(draft, null, 2) + '\n'); fs.fsyncSync(descriptor); }
  finally { fs.closeSync(descriptor); }
  fs.renameSync(temporary, destination);
  return { ...draft, saved_to: destination };
}

function callTool(name, args) {
  const values = args && typeof args === 'object' && !Array.isArray(args) ? args : {};
  try {
    if (name === 'catalog_search') {
      const query = String(values.query || '').trim().toLowerCase();
      const type = String(values.type || 'all');
      const limit = values.limit === undefined ? 20 : values.limit;
      if (!['all', 'package', 'plugin', 'fork'].includes(type) || !Number.isInteger(limit) || limit < 1 || limit > 50) throw new Error('invalid catalog filters');
      const terms = query.split(/\s+/).filter(Boolean);
      const rows = entries.filter(item => (type === 'all' || item.type === type) && terms.every(term => JSON.stringify(item).toLowerCase().includes(term)));
      return result({ count: rows.length, results: rows.slice(0, limit) });
    }
    if (name === 'catalog_compare') {
      if (!Array.isArray(values.ids) || values.ids.length < 1 || values.ids.length > 8) throw new Error('choose one to eight identities');
      const wanted = new Set(values.ids.map(String));
      const rows = entries.filter(item => wanted.has(String(item.id)));
      const found = new Set(rows.map(item => String(item.id)));
      return result({ artifacts: rows, missing: [...wanted].filter(id => !found.has(id)).sort(), verification: 'metadata-only' });
    }
    if (name === 'configuration_save_draft') return result(saveDraft(values));
    return result({ error: 'unknown tool' }, true);
  } catch (error) {
    return result({ error: error instanceof Error ? error.message : 'tool failed' }, true);
  }
}

function dispatch(message) {
  if (!message || typeof message !== 'object' || message.jsonrpc !== '2.0') return { jsonrpc: '2.0', id: null, error: { code: -32600, message: 'Invalid Request' } };
  if (message.id === undefined || message.id === null) return null;
  const params = message.params && typeof message.params === 'object' ? message.params : {};
  let value;
  if (message.method === 'initialize') {
    // This small server implements the connection-level initialize handshake.
    // MCP 2026-07-28 uses per-request negotiation, so do not advertise it.
    const supported = new Set(['2025-06-18', '2025-03-26', '2024-11-05']);
    const requested = String(params.protocolVersion || '');
    value = {
      protocolVersion: supported.has(requested) ? requested : '2025-06-18',
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: 'dsh-forge-assistant', version: '0.1.0' },
      instructions: 'Search and compare catalog evidence, explain compatibility and risk gaps, and save only inert drafts. Never claim verification, install packages, or run code.',
    };
  } else if (message.method === 'ping') value = {};
  else if (message.method === 'tools/list') value = { tools };
  else if (message.method === 'tools/call') value = callTool(String(params.name || ''), params.arguments);
  else return { jsonrpc: '2.0', id: message.id, error: { code: -32601, message: 'Method not found' } };
  return { jsonrpc: '2.0', id: message.id, result: value };
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity, terminal: false });
input.on('line', line => {
  let response;
  try { response = dispatch(JSON.parse(line)); }
  catch { response = { jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error' } }; }
  if (response) process.stdout.write(JSON.stringify(response) + '\n');
});
