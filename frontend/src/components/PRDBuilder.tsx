import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

interface Section {
  id: string;
  title: string;
  order: number;
  prompt: string;
  fields: string[];
  example: string;
}

interface PRDBuilderProps {
  onBack: () => void;
}

const PRDBuilder: React.FC<PRDBuilderProps> = ({ onBack }) => {
  const [sections, setSections] = useState<Section[]>([]);
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [sectionContents, setSectionContents] = useState<{[key: string]: string}>({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [feedback, setFeedback] = useState('');
  const [context] = useState({
    product_name: "AKS Feature",
    target_users: "DevOps Engineers",
    problem_statement: "Need better monitoring"
  });

  useEffect(() => {
    fetchSections();
  }, []);

  const fetchSections = async () => {
    try {
      const response = await fetch('/api/prd/sections');
      const data = await response.json();
      setSections(data.sections.sort((a: Section, b: Section) => a.order - b.order));
    } catch (error) {
      console.error('Error fetching sections:', error);
    }
  };

  const generateSection = async () => {
    if (currentSectionIndex >= sections.length) return;
    
    setIsGenerating(true);
    const currentSection = sections[currentSectionIndex];
    
    try {
      const response = await fetch('/api/prd/generate-section', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section_id: currentSection.id,
          context: context,
          previous_sections: sectionContents
        })
      });
      
      const data = await response.json();
      setSectionContents(prev => ({
        ...prev,
        [currentSection.id]: data.content
      }));
    } catch (error) {
      console.error('Error generating section:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const regenerateSection = async () => {
    const currentSection = sections[currentSectionIndex];
    setIsGenerating(true);
    
    try {
      const response = await fetch('/api/prd/regenerate-section', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          section_id: currentSection.id,
          context: context,
          previous_sections: sectionContents,
          feedback: feedback
        })
      });
      
      const data = await response.json();
      setSectionContents(prev => ({
        ...prev,
        [currentSection.id]: data.content
      }));
      setFeedback('');
    } catch (error) {
      console.error('Error regenerating section:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const acceptSection = () => {
    if (isEditing) {
      setSectionContents(prev => ({
        ...prev,
        [sections[currentSectionIndex].id]: editContent
      }));
      setIsEditing(false);
    }
    
    if (currentSectionIndex < sections.length - 1) {
      setCurrentSectionIndex(currentSectionIndex + 1);
      setTimeout(() => generateSection(), 100);
    }
  };

  const startEditing = () => {
    setIsEditing(true);
    setEditContent(sectionContents[sections[currentSectionIndex]?.id] || '');
  };

  const currentSection = sections[currentSectionIndex];
  const currentContent = sectionContents[currentSection?.id];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <button
        onClick={onBack}
        className="mb-4 text-blue-600 hover:text-blue-800 flex items-center"
      >
        ← Back to Agent Selection
      </button>

      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-8 text-gray-800">PRD Builder</h1>
        
        {/* Progress */}
        <div className="mb-8 flex flex-wrap gap-2">
          {sections.map((section, index) => (
            <span
              key={section.id}
              className={`px-3 py-1 rounded-full text-sm ${
                index < currentSectionIndex
                  ? 'bg-green-500 text-white'
                  : index === currentSectionIndex
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-300 text-gray-600'
              }`}
            >
              {section.title}
            </span>
          ))}
        </div>

        {/* Current Section */}
        {currentSection && currentSectionIndex < sections.length && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
            <h2 className="text-2xl font-semibold mb-4">
              Section {currentSectionIndex + 1}: {currentSection.title}
            </h2>

            {!currentContent && !isGenerating && (
              <button
                onClick={generateSection}
                className="bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600"
              >
                Generate {currentSection.title}
              </button>
            )}

            {isGenerating && (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
                <p className="mt-4 text-gray-600">Generating {currentSection.title}...</p>
              </div>
            )}

            {currentContent && !isEditing && (
              <div>
                <div className="prose max-w-none mb-6">
                  <ReactMarkdown>{currentContent}</ReactMarkdown>
                </div>
                
                <div className="flex gap-3 mb-4">
                  <button
                    onClick={acceptSection}
                    className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                  >
                    Accept & Continue
                  </button>
                  <button
                    onClick={startEditing}
                    className="bg-yellow-500 text-white px-4 py-2 rounded hover:bg-yellow-600"
                  >
                    Edit
                  </button>
                </div>

                <div className="border-t pt-4">
                  <textarea
                    placeholder="Provide feedback for regeneration..."
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    className="w-full p-3 border rounded-lg mb-2"
                    rows={3}
                  />
                  <button
                    onClick={regenerateSection}
                    disabled={!feedback}
                    className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-gray-300"
                  >
                    Regenerate with Feedback
                  </button>
                </div>
              </div>
            )}

            {isEditing && (
              <div>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full p-3 border rounded-lg mb-4"
                  rows={10}
                />
                <div className="flex gap-3">
                  <button
                    onClick={acceptSection}
                    className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
                  >
                    Save & Continue
                  </button>
                  <button
                    onClick={() => setIsEditing(false)}
                    className="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Complete PRD */}
        {currentSectionIndex >= sections.length && sections.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="bg-green-100 border-l-4 border-green-500 p-4 mb-6">
              <p className="text-green-700 font-semibold">PRD Generation Complete!</p>
              <p className="text-green-600">All sections have been generated and approved.</p>
            </div>
            
            {sections.map(section => (
              <div key={section.id} className="mb-8">
                <h2 className="text-2xl font-semibold mb-3">{section.title}</h2>
                <div className="prose max-w-none">
                  <ReactMarkdown>{sectionContents[section.id]}</ReactMarkdown>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PRDBuilder;