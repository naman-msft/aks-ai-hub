import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Copy, Check, ArrowLeft, FileText, Search, Edit, Eye, Download } from 'lucide-react';

interface BlogAgentProps {
  onBack: () => void;
}

interface BlogType {
  id: string;
  name: string;
  description: string;
  guidelines: string;
  audience: string;
}

interface BlogMetadata {
  estimated_read_time: number;
  word_count: number;
  has_code_blocks: boolean;
  has_images: boolean;
  has_links: boolean;
  has_front_matter?: boolean;
  front_matter?: string;
}

interface StructuredFeedback {
  overall_assessment: string;
  strengths: string[];
  improvements: string[];
  suggestions: string[];
  publishing_readiness: string;
}

const BlogAgent: React.FC<BlogAgentProps> = ({ onBack }) => {
  const [step, setStep] = useState<'select' | 'create' | 'review' | 'results'>('select');
  const [mode, setMode] = useState<'create' | 'review'>('create');
  const [blogTypes, setBlogTypes] = useState<BlogType[]>([]);
  const [selectedBlogType, setSelectedBlogType] = useState<string>('');
  const [title, setTitle] = useState('');
  const [rawContent, setRawContent] = useState('');
  const [targetAudience, setTargetAudience] = useState('');
  const [additionalContext, setAdditionalContext] = useState('');
  const [blogContent, setBlogContent] = useState('');
  const [reviewContent, setReviewContent] = useState('');
  const [structuredFeedback, setStructuredFeedback] = useState<StructuredFeedback | null>(null);
  const [metadata, setMetadata] = useState<BlogMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [previewMode, setPreviewMode] = useState<'markdown' | 'preview'>('preview');

  useEffect(() => {
    fetchBlogTypes();
  }, []);

  const fetchBlogTypes = async () => {
    try {
      const response = await fetch('/api/blog/types');
      const data = await response.json();
      if (data.blog_types) {
        setBlogTypes(data.blog_types);
      }
    } catch (err) {
      console.error('Failed to fetch blog types:', err);
      setError('Failed to load blog types');
    }
  };

  const handleCreateBlog = async () => {
    if (!selectedBlogType || !rawContent.trim()) {
      setError('Please select a blog type and provide content');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/blog/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          blog_type: selectedBlogType,
          raw_content: rawContent,
          title: title,
          target_audience: targetAudience,
          additional_context: additionalContext,
        }),
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else {
        setBlogContent(data.blog_content);
        setMetadata(data.metadata);
        setStep('results');
      }
    } catch (err) {
      setError('Failed to create blog post. Please try again.');
      console.error('Create blog error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewBlog = async () => {
    if (!selectedBlogType || !blogContent.trim()) {
      setError('Please select a blog type and provide blog content to review');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/blog/review', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          blog_content: blogContent,
          blog_type: selectedBlogType,
        }),
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else {
        setReviewContent(data.review);
        setStructuredFeedback(data.structured_feedback);
        setStep('results');
      }
    } catch (err) {
      setError('Failed to review blog post. Please try again.');
      console.error('Review blog error:', err);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const downloadAsMarkdown = () => {
    const content = mode === 'create' ? blogContent : `# Review\n\n${reviewContent}`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `blog-${mode}-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const resetForm = () => {
    setStep('select');
    setMode('create');
    setSelectedBlogType('');
    setTitle('');
    setRawContent('');
    setTargetAudience('');
    setAdditionalContext('');
    setBlogContent('');
    setReviewContent('');
    setStructuredFeedback(null);
    setMetadata(null);
    setError(null);
    setCopySuccess(false);
  };

  const selectedBlogTypeData = blogTypes.find(bt => bt.id === selectedBlogType);

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-100 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={onBack}
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
                <span>Back to Agents</span>
              </button>
              <div>
                <h1 className="text-3xl font-bold text-gray-800 flex items-center">
                  <FileText className="w-8 h-8 mr-3 text-purple-600" />
                  Blog Writer
                </h1>
                <p className="text-gray-600">Create and review technical blog posts for multiple platforms</p>
              </div>
            </div>
            {step === 'results' && (
              <button
                onClick={resetForm}
                className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors"
              >
                New Blog Post
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Mode Selection */}
        {step === 'select' && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Choose Mode</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => {
                  setMode('create');
                  setStep('create');
                }}
                className="p-6 border-2 border-purple-200 rounded-lg hover:border-purple-400 transition-colors text-left group"
              >
                <div className="flex items-center mb-3">
                  <Edit className="w-6 h-6 text-purple-600 mr-3" />
                  <h3 className="text-lg font-semibold">Create Blog Post</h3>
                </div>
                <p className="text-gray-600">Transform raw content into polished blog posts for different platforms</p>
              </button>
              
              <button
                onClick={() => {
                  setMode('review');
                  setStep('review');
                }}
                className="p-6 border-2 border-blue-200 rounded-lg hover:border-blue-400 transition-colors text-left group"
              >
                <div className="flex items-center mb-3">
                  <Search className="w-6 h-6 text-blue-600 mr-3" />
                  <h3 className="text-lg font-semibold">Review Blog Post</h3>
                </div>
                <p className="text-gray-600">Get detailed feedback on existing blog posts for specific platforms</p>
              </button>
            </div>
          </div>
        )}

        {/* Blog Type Selection */}
        {(step === 'create' || step === 'review') && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Select Blog Platform</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {blogTypes.map((blogType) => (
                <div
                  key={blogType.id}
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                    selectedBlogType === blogType.id
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-gray-200 hover:border-purple-300'
                  }`}
                  onClick={() => setSelectedBlogType(blogType.id)}
                >
                  <h3 className="font-semibold text-lg mb-2">{blogType.name}</h3>
                  <p className="text-gray-600 text-sm mb-2">{blogType.description}</p>
                  <p className="text-xs text-gray-500 mb-2">
                    <strong>Audience:</strong> {blogType.audience}
                  </p>
                  <p className="text-xs text-gray-500">
                    <strong>Guidelines:</strong> {blogType.guidelines}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Create Blog Form */}
        {step === 'create' && selectedBlogType && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Create Blog Post</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Title (Optional - will be generated if empty)
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter blog post title"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Raw Content *
                </label>
                <textarea
                  value={rawContent}
                  onChange={(e) => setRawContent(e.target.value)}
                  placeholder="Paste your raw content, notes, or ideas here. The agent will research and expand this into a complete blog post."
                  rows={8}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Audience (Optional)
                </label>
                <input
                  type="text"
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  placeholder="e.g., DevOps engineers, Platform architects"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Additional Context (Optional)
                </label>
                <textarea
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  placeholder="Any additional context, requirements, or specific points to include"
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>

              {selectedBlogTypeData && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-semibold text-blue-800 mb-2">
                    {selectedBlogTypeData.name} Guidelines
                  </h4>
                  <p className="text-blue-700 text-sm">{selectedBlogTypeData.guidelines}</p>
                </div>
              )}

              <button
                onClick={handleCreateBlog}
                disabled={loading || !rawContent.trim()}
                className="w-full bg-purple-600 text-white py-3 rounded-lg hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                    Creating Blog Post...
                  </>
                ) : (
                  'Create Blog Post'
                )}
              </button>
            </div>
          </div>
        )}

        {/* Review Blog Form */}
        {step === 'review' && selectedBlogType && (
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Review Blog Post</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Blog Content to Review *
                </label>
                <textarea
                  value={blogContent}
                  onChange={(e) => setBlogContent(e.target.value)}
                  placeholder="Paste your blog post content here for review and feedback"
                  rows={12}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-sm"
                />
              </div>

              {selectedBlogTypeData && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-semibold text-blue-800 mb-2">
                    Review Criteria for {selectedBlogTypeData.name}
                  </h4>
                  <p className="text-blue-700 text-sm">{selectedBlogTypeData.guidelines}</p>
                </div>
              )}

              <button
                onClick={handleReviewBlog}
                disabled={loading || !blogContent.trim()}
                className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                    Reviewing Blog Post...
                  </>
                ) : (
                  'Review Blog Post'
                )}
              </button>
            </div>
          </div>
        )}

        {/* Results */}
        {step === 'results' && (
          <div className="space-y-6">
            {/* Metadata Display */}
            {metadata && mode === 'create' && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Blog Post Metadata</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div className="bg-gray-50 p-3 rounded">
                    <span className="font-medium">Word Count:</span>
                    <div className="text-lg font-bold text-purple-600">{metadata.word_count}</div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <span className="font-medium">Read Time:</span>
                    <div className="text-lg font-bold text-purple-600">{metadata.estimated_read_time} min</div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <span className="font-medium">Code Blocks:</span>
                    <div className="text-lg font-bold text-purple-600">
                      {metadata.has_code_blocks ? '✓' : '✗'}
                    </div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <span className="font-medium">Images:</span>
                    <div className="text-lg font-bold text-purple-600">
                      {metadata.has_images ? '✓' : '✗'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Structured Feedback Display */}
            {structuredFeedback && mode === 'review' && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Review Summary</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-semibold text-green-700 mb-2">Strengths</h4>
                    <ul className="space-y-1">
                      {structuredFeedback.strengths.map((strength, index) => (
                        <li key={index} className="text-sm text-green-600 flex items-start">
                          <span className="text-green-500 mr-2">•</span>
                          {strength}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="font-semibold text-orange-700 mb-2">Areas for Improvement</h4>
                    <ul className="space-y-1">
                      {structuredFeedback.improvements.map((improvement, index) => (
                        <li key={index} className="text-sm text-orange-600 flex items-start">
                          <span className="text-orange-500 mr-2">•</span>
                          {improvement}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                {structuredFeedback.publishing_readiness && (
                  <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                    <span className="font-semibold text-blue-800">Publishing Readiness: </span>
                    <span className="text-blue-700">{structuredFeedback.publishing_readiness}</span>
                  </div>
                )}
              </div>
            )}

            {/* Content Display */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">
                  {mode === 'create' ? 'Generated Blog Post' : 'Review Feedback'}
                </h3>
                <div className="flex items-center space-x-2">
                  {mode === 'create' && (
                    <div className="flex border border-gray-300 rounded-lg">
                      <button
                        onClick={() => setPreviewMode('preview')}
                        className={`px-3 py-1 text-sm rounded-l-lg ${
                          previewMode === 'preview'
                            ? 'bg-purple-600 text-white'
                            : 'bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        <Eye className="w-4 h-4 inline mr-1" />
                        Preview
                      </button>
                      <button
                        onClick={() => setPreviewMode('markdown')}
                        className={`px-3 py-1 text-sm rounded-r-lg ${
                          previewMode === 'markdown'
                            ? 'bg-purple-600 text-white'
                            : 'bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        <FileText className="w-4 h-4 inline mr-1" />
                        Markdown
                      </button>
                    </div>
                  )}
                  <button
                    onClick={downloadAsMarkdown}
                    className="flex items-center space-x-1 bg-green-600 text-white px-3 py-1 rounded-lg hover:bg-green-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download</span>
                  </button>
                  <button
                    onClick={() => copyToClipboard(mode === 'create' ? blogContent : reviewContent)}
                    className="flex items-center space-x-1 bg-purple-600 text-white px-3 py-1 rounded-lg hover:bg-purple-700 transition-colors"
                  >
                    {copySuccess ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    <span>{copySuccess ? 'Copied!' : 'Copy'}</span>
                  </button>
                </div>
              </div>

              <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-lg p-4">
                {mode === 'create' ? (
                  previewMode === 'preview' ? (
                    <div className="prose max-w-none">
                      <ReactMarkdown>{blogContent}</ReactMarkdown>
                    </div>
                  ) : (
                    <pre className="whitespace-pre-wrap text-sm font-mono">{blogContent}</pre>
                  )
                ) : (
                  <div className="prose max-w-none">
                    <ReactMarkdown>{reviewContent}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BlogAgent;