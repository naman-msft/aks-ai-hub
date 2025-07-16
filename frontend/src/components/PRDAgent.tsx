import React, { useState } from 'react';
import { 
  FileText, 
  MessageSquare, 
  ArrowLeft, 
  Download, 
  Copy, 
  Loader2, 
  Upload, 
  Link, 
  Plus,
  X,
  ChevronRight,
  ArrowRight,
  CheckCircle
} from 'lucide-react';

interface PRDAgentProps {
  onBack: () => void;
}

interface DataSource {
  id: string;
  type: 'file' | 'url' | 'text';
  name: string;
  content: string;
  status: 'ready' | 'processing' | 'error';
}

const PRDAgent: React.FC<PRDAgentProps> = ({ onBack }) => {
  const [step, setStep] = useState<'select' | 'create' | 'review' | 'data-sources'>('select');
  const [mode, setMode] = useState<'create' | 'review'>('create');
  const [prompt, setPrompt] = useState('');
  const [prdText, setPrdText] = useState('');
  const [prdFile, setPrdFile] = useState<File | null>(null);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newUrl, setNewUrl] = useState('');
  const [newTextContent, setNewTextContent] = useState('');
  const [reviewMode, setReviewMode] = useState<'text' | 'file'>('text');

  const createPRD = async () => {
    if (!prompt.trim()) {
      setError('Please enter a description for your PRD');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Prepare context from data sources
      const contextData = dataSources.map(ds => ({
        type: ds.type,
        name: ds.name,
        content: ds.content
      }));

      const response = await fetch('/api/prd/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: prompt,
          context: 'AKS PRD creation',
          data_sources: contextData
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to create PRD');
      }

      const data = await response.json();
      setResult(data);
      setStep('create');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create PRD');
    } finally {
      setLoading(false);
    }
  };

  const reviewPRD = async () => {
    let prdContent = '';
    
    if (reviewMode === 'file' && prdFile) {
      // Read file content
      const fileContent = await readFileContent(prdFile);
      prdContent = fileContent;
    } else if (reviewMode === 'text' && prdText.trim()) {
      prdContent = prdText;
    } else {
      setError('Please provide PRD content to review');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/prd/review', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prd_text: prdContent
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to review PRD');
      }

      const data = await response.json();
      setResult(data);
      setStep('review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to review PRD');
    } finally {
      setLoading(false);
    }
  };

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  };

  const addDataSource = (type: 'file' | 'url' | 'text', name: string, content: string) => {
    const newSource: DataSource = {
      id: Date.now().toString(),
      type,
      name,
      content,
      status: 'ready'
    };
    setDataSources([...dataSources, newSource]);
  };

  const removeDataSource = (id: string) => {
    setDataSources(dataSources.filter(ds => ds.id !== id));
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        addDataSource('file', file.name, content);
      };
      reader.readAsText(file);
    }
  };

  const handleUrlAdd = () => {
    if (newUrl.trim()) {
      addDataSource('url', newUrl, newUrl);
      setNewUrl('');
    }
  };

  const handleTextAdd = () => {
    if (newTextContent.trim()) {
      addDataSource('text', 'Custom Text', newTextContent);
      setNewTextContent('');
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      alert('Copied to clipboard!');
    } catch (err) {
      setError('Failed to copy to clipboard');
    }
  };

  const resetForm = () => {
    setPrompt('');
    setPrdText('');
    setPrdFile(null);
    setDataSources([]);
    setResult(null);
    setError(null);
    setNewUrl('');
    setNewTextContent('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          {/* Header with Back Button */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={onBack}
                className="flex items-center px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                <ArrowLeft className="h-5 w-5 mr-2" />
                Back to Hub
              </button>
              <div className="flex items-center">
                <FileText className="h-10 w-10 text-blue-600 mr-3" />
                <h1 className="text-4xl font-bold text-gray-900">PRD Writer & Reviewer</h1>
              </div>
              <div className="w-32"></div> {/* Spacer for center alignment */}
            </div>
            <p className="text-center text-lg text-gray-600">
              AI-powered Product Requirements Document creation and review
            </p>
          </div>

          {/* Progress Steps */}
          <div className="flex justify-center mb-8">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setStep('select')}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === 'select' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                }`}
              >
                <MessageSquare className="h-5 w-5 mr-2" />
                <span className="font-medium">Select Mode</span>
              </button>
              
              <ArrowRight className="h-5 w-5 text-gray-400" />
              
              <button
                onClick={() => setStep('data-sources')}
                disabled={step === 'select'}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === 'data-sources' 
                    ? 'bg-blue-600 text-white' 
                    : step === 'select' 
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                    : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                }`}
              >
                <Plus className="h-5 w-5 mr-2" />
                <span className="font-medium">Data Sources</span>
              </button>
              
              <ArrowRight className="h-5 w-5 text-gray-400" />
              
              <button
                onClick={() => setStep(mode)}
                disabled={step === 'select'}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === mode 
                    ? 'bg-blue-600 text-white' 
                    : step === 'select' 
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                    : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                }`}
              >
                <FileText className="h-5 w-5 mr-2" />
                <span className="font-medium">{mode === 'create' ? 'Create' : 'Review'}</span>
              </button>
            </div>
          </div>

          {/* Mode Selection */}
          {step === 'select' && (
            <div className="bg-white rounded-lg shadow-lg p-8">
              <h3 className="text-2xl font-bold text-center mb-6">What would you like to do?</h3>
              <div className="flex justify-center space-x-6">
                <button
                  className="flex flex-col items-center p-6 bg-blue-50 border-2 border-blue-200 rounded-lg hover:bg-blue-100 hover:border-blue-300 transition-colors"
                  onClick={() => {
                    setMode('create');
                    setStep('data-sources');
                    resetForm();
                  }}
                >
                  <FileText className="h-12 w-12 text-blue-600 mb-3" />
                  <h4 className="text-lg font-semibold text-gray-900 mb-2">Create New PRD</h4>
                  <p className="text-sm text-gray-600 text-center">
                    Generate a comprehensive PRD from your requirements
                  </p>
                </button>
                <button
                  className="flex flex-col items-center p-6 bg-green-50 border-2 border-green-200 rounded-lg hover:bg-green-100 hover:border-green-300 transition-colors"
                  onClick={() => {
                    setMode('review');
                    setStep('review');
                    resetForm();
                  }}
                >
                  <MessageSquare className="h-12 w-12 text-green-600 mb-3" />
                  <h4 className="text-lg font-semibold text-gray-900 mb-2">Review Existing PRD</h4>
                  <p className="text-sm text-gray-600 text-center">
                    Get feedback and suggestions for your PRD
                  </p>
                </button>
              </div>
            </div>
          )}

          {/* Data Sources Step */}
          {step === 'data-sources' && mode === 'create' && (
            <div className="bg-white rounded-lg shadow-lg p-8">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold">Add Data Sources (Optional)</h3>
                <button
                  onClick={() => setStep('create')}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Continue to Create PRD
                </button>
              </div>
              
              <p className="text-gray-600 mb-6">
                Add relevant documents, URLs, or text content to help the AI create a better PRD
              </p>

              {/* Data Source Options */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                {/* File Upload */}
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <h4 className="font-semibold mb-2">Upload Documents</h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Upload existing docs, specs, or requirements
                  </p>
                  <input
                    type="file"
                    accept=".txt,.doc,.docx,.pdf,.md"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="file-upload"
                  />
                  <label
                    htmlFor="file-upload"
                    className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
                  >
                    Choose File
                  </label>
                </div>

                {/* URL Input */}
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                  <Link className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <h4 className="font-semibold mb-2">Add URLs</h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Reference documentation or specs online
                  </p>
                  <div className="flex space-x-2">
                    <input
                      type="url"
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      placeholder="https://..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <button
                      onClick={handleUrlAdd}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Add
                    </button>
                  </div>
                </div>

                {/* Text Input */}
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
                  <FileText className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <h4 className="font-semibold mb-2">Paste Content</h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Add relevant text content directly
                  </p>
                  <textarea
                    value={newTextContent}
                    onChange={(e) => setNewTextContent(e.target.value)}
                    placeholder="Paste your content here..."
                    className="w-full h-20 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  />
                  <button
                    onClick={handleTextAdd}
                    className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors w-full"
                  >
                    Add Text
                  </button>
                </div>
              </div>

              {/* Data Sources List */}
              {dataSources.length > 0 && (
                <div className="border-t pt-6">
                  <h4 className="font-semibold mb-4">Added Data Sources ({dataSources.length})</h4>
                  <div className="space-y-3">
                    {dataSources.map((source) => (
                      <div key={source.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center">
                          {source.type === 'file' && <Upload className="h-5 w-5 text-blue-600 mr-3" />}
                          {source.type === 'url' && <Link className="h-5 w-5 text-green-600 mr-3" />}
                          {source.type === 'text' && <FileText className="h-5 w-5 text-purple-600 mr-3" />}
                          <div>
                            <div className="font-medium">{source.name}</div>
                            <div className="text-sm text-gray-600 capitalize">{source.type}</div>
                          </div>
                        </div>
                        <button
                          onClick={() => removeDataSource(source.id)}
                          className="text-red-600 hover:text-red-800 transition-colors"
                        >
                          <X className="h-5 w-5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Create PRD Step */}
          {step === 'create' && (
            <div className="bg-white rounded-lg shadow-lg p-8">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold">Create New PRD</h3>
                <button
                  onClick={() => setStep('data-sources')}
                  className="text-blue-600 hover:text-blue-800 transition-colors"
                >
                  ← Back to Data Sources
                </button>
              </div>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Describe what you want to build
                  </label>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Example: A new auto-scaling feature for AKS that automatically adjusts node pools based on workload patterns and resource utilization..."
                    className="w-full h-32 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                {dataSources.length > 0 && (
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="flex items-center mb-2">
                      <CheckCircle className="h-5 w-5 text-blue-600 mr-2" />
                      <span className="font-medium text-blue-900">
                        Using {dataSources.length} data source{dataSources.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <p className="text-sm text-blue-700">
                      The AI will use your uploaded documents and references to create a more comprehensive PRD.
                    </p>
                  </div>
                )}

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-700">{error}</p>
                  </div>
                )}

                <button
                  onClick={createPRD}
                  disabled={loading || !prompt.trim()}
                  className="w-full flex items-center justify-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Creating PRD...
                    </>
                  ) : (
                    <>
                      <FileText className="h-5 w-5 mr-2" />
                      Create PRD
                    </>
                  )}
                </button>
              </div>

              {/* PRD Result */}
              {result && result.prd && (
                <div className="mt-8 border-t pt-8">
                  <div className="flex items-center justify-between mb-6">
                    <h4 className="text-xl font-bold text-green-700">✅ PRD Created Successfully!</h4>
                    <div className="flex items-center space-x-3">
                      <button
                        onClick={() => copyToClipboard(result.prd)}
                        className="flex items-center px-4 py-2 text-blue-600 hover:text-blue-800 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
                      >
                        <Copy className="h-4 w-4 mr-2" />
                        Copy PRD
                      </button>
                      <button
                        onClick={() => {
                          resetForm();
                          setStep('select');
                        }}
                        className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Create Another
                      </button>
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm font-mono">{result.prd}</pre>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Review PRD Step */}
          {step === 'review' && (
            <div className="bg-white rounded-lg shadow-lg p-8">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold">Review Existing PRD</h3>
                <button
                  onClick={() => setStep('select')}
                  className="text-blue-600 hover:text-blue-800 transition-colors"
                >
                  ← Back to Selection
                </button>
              </div>
              
              <div className="space-y-6">
                {/* Review Mode Selection */}
                <div className="flex space-x-4 mb-6">
                  <button
                    onClick={() => setReviewMode('text')}
                    className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                      reviewMode === 'text' 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                    }`}
                  >
                    <FileText className="h-5 w-5 mr-2" />
                    Paste Text
                  </button>
                  <button
                    onClick={() => setReviewMode('file')}
                    className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                      reviewMode === 'file' 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                    }`}
                  >
                    <Upload className="h-5 w-5 mr-2" />
                    Upload File
                  </button>
                </div>

                {/* Text Input Mode */}
                {reviewMode === 'text' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Paste your PRD text here
                    </label>
                    <textarea
                      value={prdText}
                      onChange={(e) => setPrdText(e.target.value)}
                      placeholder="Paste your existing PRD content here..."
                      className="w-full h-48 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                )}

                {/* File Upload Mode */}
                {reviewMode === 'file' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Upload your PRD document
                    </label>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                      <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm text-gray-600 mb-4">
                        {prdFile ? `Selected: ${prdFile.name}` : 'Select a PRD file to upload'}
                      </p>
                      <input
                        type="file"
                        accept=".txt,.doc,.docx,.pdf,.md"
                        onChange={(e) => setPrdFile(e.target.files?.[0] || null)}
                        className="hidden"
                        id="prd-file-upload"
                      />
                      <label
                        htmlFor="prd-file-upload"
                        className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
                      >
                        Choose File
                      </label>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-700">{error}</p>
                  </div>
                )}

                <button
                  onClick={reviewPRD}
                  disabled={loading || (reviewMode === 'text' && !prdText.trim()) || (reviewMode === 'file' && !prdFile)}
                  className="w-full flex items-center justify-center px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Reviewing PRD...
                    </>
                  ) : (
                    <>
                      <MessageSquare className="h-5 w-5 mr-2" />
                      Review PRD
                    </>
                  )}
                </button>
              </div>

              {/* Review Result */}
              {result && result.review && (
                <div className="mt-8 border-t pt-8">
                  <div className="flex items-center justify-between mb-6">
                    <h4 className="text-xl font-bold text-green-700">✅ PRD Review Complete!</h4>
                    <div className="flex items-center space-x-3">
                      {result.score && (
                        <div className="text-sm">
                          <span className="font-medium">Quality Score: </span>
                          <span className={`font-bold text-lg ${result.score >= 80 ? 'text-green-600' : result.score >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {result.score}/100
                          </span>
                        </div>
                      )}
                      <button
                        onClick={() => copyToClipboard(result.review)}
                        className="flex items-center px-4 py-2 text-blue-600 hover:text-blue-800 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
                      >
                        <Copy className="h-4 w-4 mr-2" />
                        Copy Review
                      </button>
                      <button
                        onClick={() => {
                          resetForm();
                          setStep('select');
                        }}
                        className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Review Another
                      </button>
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-6 max-h-96 overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm font-mono">{result.review}</pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PRDAgent;