# AKS AI Hub

A modern web application platform for multiple AI-powered assistants. Currently supports AKS customer support responses with optional human comparison and evaluation. Easily extensible for additional assistants like PRD writing, documentation, and more.

## Features

- **Multi-Assistant Platform**: Extensible architecture for multiple AI assistants
- **AI Response Generation**: Instant AI-powered responses with streaming
- **Human vs AI Comparison**: Optional detailed evaluation and comparison
- **Copy-to-Clipboard**: Easy copying of responses for external use
- **Markdown Support**: Beautiful rendering of formatted responses
- **Evaluation Analytics**: Detailed scoring and analysis
- **Extensible Design**: Ready for additional assistant types

## Current Assistants

- **AKS Support Assistant**: Generate responses to Azure Kubernetes Service customer emails
- **Future**: PRD Writer, Documentation Assistant, Code Review Assistant, etc.

## Tech Stack

- **Frontend**: React with TypeScript
- **Backend**: Flask Python API
- **AI**: OpenAI GPT-5 with custom assistants and vector stores
- **Deployment**: Azure App Service

## Architecture

React UI (Dashboard) --> Flask API (Hub) --> OpenAI API (Assistants)

## License

MIT License
