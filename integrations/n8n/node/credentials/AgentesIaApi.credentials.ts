import type {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	Icon,
	INodeProperties,
} from 'n8n-workflow';

export class AgentesIaApi implements ICredentialType {
	name = 'agentesIaApi';

	displayName = 'Agentes IA API';

	icon: Icon = {
		light: 'file:../nodes/AgentesIa/agentesIa.svg',
		dark: 'file:../nodes/AgentesIa/agentesIa.dark.svg',
	};

	documentationUrl =
		'https://github.com/ricardoprs76/agentes-ia-empresas/tree/main/integrations/n8n/node#credentials';

	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'http://localhost:8000',
			placeholder: 'http://agente:8000',
			description: 'Where the agent server (agentes serve) is listening',
			required: true,
		},
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			description: 'Value of AGENTES_API_KEY on the agent server; leave empty if it has none',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				'X-API-Key': '={{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/health',
		},
	};
}
