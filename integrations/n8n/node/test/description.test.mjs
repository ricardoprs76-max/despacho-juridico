// Checks the compiled node and credential against the agent's HTTP API contract.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const { AgentesIa } = require('../dist/nodes/AgentesIa/AgentesIa.node.js');
const { AgentesIaApi } = require('../dist/credentials/AgentesIaApi.credentials.js');

const node = new AgentesIa().description;
const credential = new AgentesIaApi();

function operations(resource) {
	const prop = node.properties.find(
		(p) => p.name === 'operation' && p.displayOptions?.show?.resource?.includes(resource),
	);
	assert.ok(prop, `no operation list for ${resource}`);
	return Object.fromEntries(prop.options.map((o) => [o.value, o.routing?.request]));
}

function param(name, operation) {
	return node.properties.find(
		(p) => p.name === name && p.displayOptions?.show?.operation?.includes(operation),
	);
}

test('node identity', () => {
	assert.equal(node.name, 'agentesIa');
	assert.equal(node.displayName, 'Agentes IA para Empresas');
	assert.equal(node.usableAsTool, true);
	assert.deepEqual(node.credentials, [{ name: 'agentesIaApi', required: true }]);
	assert.equal(node.requestDefaults.baseURL, '={{$credentials.baseUrl}}');
});

test('resources', () => {
	const resource = node.properties.find((p) => p.name === 'resource');
	assert.deepEqual(
		resource.options.map((o) => o.value),
		['conversation', 'audit'],
	);
});

test('conversation operations route to the chat API', () => {
	const ops = operations('conversation');
	assert.deepEqual(Object.keys(ops), ['sendMessage', 'confirm', 'getHistory']);
	assert.deepEqual(ops.sendMessage, { method: 'POST', url: '/chat' });
	assert.deepEqual(ops.confirm, { method: 'POST', url: '=/chat/{{$parameter.threadId}}/confirm' });
	assert.deepEqual(ops.getHistory, { method: 'GET', url: '=/chat/{{$parameter.threadId}}' });
});

test('message, thread and approval go in the JSON body', () => {
	const message = param('message', 'sendMessage');
	assert.equal(message.required, true);
	assert.deepEqual(message.routing.send, { type: 'body', property: 'message' });
	const thread = param('threadId', 'sendMessage');
	assert.equal(thread.routing.send.type, 'body');
	assert.equal(thread.routing.send.property, 'thread_id');
	const approved = param('approved', 'confirm');
	assert.equal(approved.type, 'boolean');
	assert.deepEqual(approved.routing.send, { type: 'body', property: 'approved' });
});

test('audit reads /audit with thread and limit', () => {
	const ops = operations('audit');
	assert.deepEqual(Object.keys(ops), ['getMany']);
	assert.deepEqual(ops.getMany, { method: 'GET', url: '/audit' });
	const limit = param('limit', 'getMany');
	assert.deepEqual(limit.typeOptions, { minValue: 1, maxValue: 500 });
	assert.equal(limit.default, 50);
	assert.deepEqual(limit.routing.send, { type: 'query', property: 'limit' });
	assert.equal(param('threadId', 'getMany').routing.send.property, 'thread_id');
});

test('credential sends X-API-Key and is tested on /health', () => {
	assert.equal(credential.name, 'agentesIaApi');
	assert.deepEqual(credential.authenticate.properties.headers, {
		'X-API-Key': '={{$credentials.apiKey}}',
	});
	assert.equal(credential.test.request.baseURL, '={{$credentials.baseUrl}}');
	assert.equal(credential.test.request.url, '/health');
	const names = credential.properties.map((p) => p.name);
	assert.deepEqual(names, ['baseUrl', 'apiKey']);
	assert.equal(credential.properties[1].typeOptions.password, true);
});
