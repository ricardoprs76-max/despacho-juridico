# n8n with the Agentes IA node preinstalled. Build context: integrations/n8n
FROM node:24-alpine AS build
WORKDIR /node
COPY node/package.json node/package-lock.json ./
RUN npm ci
COPY node ./
RUN npm run build

FROM n8nio/n8n:2.45.7
COPY --from=build --chown=node:node /node/package.json /opt/n8n-nodes-agentes-ia/package.json
COPY --from=build --chown=node:node /node/dist /opt/n8n-nodes-agentes-ia/dist
COPY --chown=node:node flows /opt/flows
ENV N8N_CUSTOM_EXTENSIONS=/opt/n8n-nodes-agentes-ia
