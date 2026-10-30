import type { INodeProperties } from 'n8n-workflow';

const forAuditGetMany = { resource: ['audit'], operation: ['getMany'] };

export const auditDescription: INodeProperties[] = [
	{
		displayName: 'Operation',
		name: 'operation',
		type: 'options',
		noDataExpression: true,
		displayOptions: { show: { resource: ['audit'] } },
		options: [
			{
				name: 'Get Many',
				value: 'getMany',
				action: 'Get many audit entries',
				description: 'Get the tool calls the agent executed, cancelled or failed, newest first',
				routing: { request: { method: 'GET', url: '/audit' } },
			},
		],
		default: 'getMany',
	},
	{
		displayName: 'Thread ID',
		name: 'threadId',
		type: 'string',
		default: '',
		description: 'Only this conversation; empty returns every conversation',
		displayOptions: { show: forAuditGetMany },
		routing: {
			send: { type: 'query', property: 'thread_id', value: '={{ $value || undefined }}' },
		},
	},
	{
		displayName: 'Limit',
		name: 'limit',
		type: 'number',
		typeOptions: { minValue: 1, maxValue: 500 },
		default: 50,
		description: 'Max number of results to return',
		displayOptions: { show: forAuditGetMany },
		routing: { send: { type: 'query', property: 'limit' } },
	},
];
