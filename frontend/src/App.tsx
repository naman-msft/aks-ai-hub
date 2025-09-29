import React, { useState, useEffect } from 'react';
import AgentSelector from './components/AgentSelector';
import EmailSupportAgent from './components/EmailSupportAgent';
import PRDAgent from './components/PRDAgent';
// import PRDBuilder from './components/PRDBuilder';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: 'active' | 'coming-soon';
}

function App() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    fetch('/api/assistants')
      .then(res => res.json())
      .then(data => setAgents(data))
      .catch(err => console.error('Failed to fetch agents:', err));
  }, []);

  const handleSelectAgent = (agentId: string) => {
    setSelectedAgent(agentId);
  };

  const handleBack = () => {
    setSelectedAgent(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {!selectedAgent && (
        <AgentSelector agents={agents} onSelectAgent={handleSelectAgent} />
      )}
      {selectedAgent === 'aks-support' && (
        <EmailSupportAgent onBack={handleBack} />
      )}
      {selectedAgent === 'prd-writer' && (
        <PRDAgent onBack={handleBack} />
      )}
      {/* {selectedAgent === 'prd-builder' && (
        <PRDBuilder onBack={handleBack} />
      )} */}
    </div>
  );
}

export default App;