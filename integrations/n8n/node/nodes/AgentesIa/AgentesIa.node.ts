import { NodeConnectionTypes, type INodeType, type INodeTypeDescription } from 'n8n-workflow';
import { auditDescription } from './resources/audit';
import { conversationDescription } from './resources/conversation';

export class AgentesIa implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Agentes IA para Empresas',
		name: 'agentesIa',
		icon: { light: 'file:agentesIa.svg', dark: 'file:agentesIa.dark.svg' },
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
		description:
			"Chat with a company's AI agent, approve or cancel its pending actions and read its audit log",
		defaults: {
			name: 'Agentes IA para Empresas',
		},
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [{ name: 'agentesIaApi', required: true }],
		requestDefaults: {
			baseURL: '={{$credentials.baseUrl}}',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			},
		},
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [
					{ name: 'Conversation', value: 'conversation' },
					{ name: 'Audit', value: 'audit' },
				],
				default: 'conversation',
			},
			...conversationDescription,
			...auditDescription,
		],
	};
}
