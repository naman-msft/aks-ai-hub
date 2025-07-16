import React from 'react';
import { Brain } from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'active' | 'coming-soon';
}

interface AgentSelectorProps {
  agents: Agent[];
  onSelectAgent: (agentId: string) => void;
}

const AgentSelector: React.FC<AgentSelectorProps> = ({ agents, onSelectAgent }) => {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <div className="flex items-center justify-center mb-4">
          <Brain className="h-10 w-10 text-blue-600 mr-3" />
          <h1 className="text-4xl font-bold text-gray-900">AKS AI Hub</h1>
        </div>
        <p className="text-lg text-gray-600">
          Choose an AI assistant to help with your tasks
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className={`p-6 rounded-lg border-2 transition-all cursor-pointer ${
              agent.status === 'active'
                ? 'border-blue-200 hover:border-blue-400 hover:shadow-lg'
                : 'border-gray-200 opacity-50 cursor-not-allowed'
            }`}
            onClick={() => agent.status === 'active' && onSelectAgent(agent.id)}
          >
            <div className="text-center">
              <div className="text-4xl mb-4">{agent.icon}</div>
              <h3 className="text-xl font-semibold mb-2">{agent.name}</h3>
              <p className="text-gray-600 mb-4">{agent.description}</p>
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${
                agent.status === 'active' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {agent.status === 'active' ? 'Available' : 'Coming Soon'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AgentSelector;