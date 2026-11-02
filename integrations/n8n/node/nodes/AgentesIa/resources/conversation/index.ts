import type { INodeProperties } from 'n8n-workflow';

const forConversation = { resource: ['conversation'] };
const THREAD_HINT = 'Letters, numbers, "-" and "_" only, up to 64 characters';

export const conversationDescription: INodeProperties[] = [
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: forConversation },
		options: [
			{
				name: 'Send Message',
				value: 'sendMessage',
				action: 'Send a message to the agent',
				description:
					'Send a message and get the reply; if the agent wants to act (e.g. send an email), the action comes back in "pending" and waits for Confirm',
				routing: { request: { method: 'POST', url: '/chat' } },
			},
			{
				name: 'Confirm',
				value: 'confirm',
				action: 'Approve or cancel the pending action',
				description: 'Approve or cancel the action the agent is waiting on in a conversation',
				routing: { request: { method: 'POST', url: '=/chat/{{$parameter.threadId}}/confirm' } },
			},
			{
				name: 'Get History',
				value: 'getHistory',
				action: 'Get the history of a conversation',
				description: 'Get the messages of a conversation and its pending action, if any',
				routing: { request: { method: 'GET', url: '=/chat/{{$parameter.threadId}}' } },
			},
		],
		default: 'sendMessage',
	},
	{
		displayName: 'Message',
		name: 'message',
		type: 'string',
		typeOptions: { rows: 3 },
		required: true,
		default: '',
		description: 'What the customer or user says to the agent',
		displayOptions: { show: { ...forConversation, operation: ['sendMessage'] } },
		routing: { send: { type: 'body', property: 'message' } },
	},
	{
		displayName: 'Thread ID',
		name: 'threadId',
		type: 'string',
		default: '',
		description: `Conversation to continue; empty starts a new one. ${THREAD_HINT}.`,
		displayOptions: { show: { ...forConversation, operation: ['sendMessage'] } },
		routing: {
			send: { type: 'body', property: 'thread_id', value: '={{ $value || undefined }}' },
		},
	},
	{
		displayName: 'Thread ID',
		name: 'threadId',
		type: 'string',
		required: true,
		default: '',
		description: `Conversation with the pending action. ${THREAD_HINT}.`,
		displayOptions: { show: { ...forConversation, operation: ['confirm', 'getHistory'] } },
	},
	{
		displayName: 'Approve',
		name: 'approved',
		type: 'boolean',
		default: false,
		description: 'Whether to run the pending action (true) or cancel it (false)',
		displayOptions: { show: { ...forConversation, operation: ['confirm'] } },
		routing: { send: { type: 'body', property: 'approved' } },
	},
];
