import React, { useState, useRef } from 'react';
import { MessageSquare, Zap, Trophy, Brain, Mail, Loader2, CheckCircle, XCircle, Copy, Plus, ArrowLeft } from 'lucide-react';
interface EmailSupportAgentProps {
  onBack: () => void;
}
interface EvaluationResult {
  evaluation_id: string;
  question: string;
  ai_response: string;
  human_response: string;
  evaluation: {
    overall_winner: string;
    overall_reasoning: string;
    scores: {
      response_a: {
        technical_accuracy: number;
        completeness: number;
        clarity: number;
        practical_value: number;
        professional_tone: number;
        evidence_citations: number;
        total: number;
      };
      response_b: {
        technical_accuracy: number;
        completeness: number;
        clarity: number;
        practical_value: number;
        professional_tone: number;
        evidence_citations: number;
        total: number;
      };
    };
    detailed_analysis: {
      response_a_strengths: string[];
      response_a_weaknesses: string[];
      response_b_strengths: string[];
      response_b_weaknesses: string[];
    };
    specific_feedback: {
      response_a: string;
      response_b: string;
    };
  };
  labels: {
    response_a: string;
    response_b: string;
  };
  winner: string;
  timestamp: string;
}

const EmailSupportAgent: React.FC<EmailSupportAgentProps> = ({ onBack }) => {
  const [emailContent, setEmailContent] = useState('');
  const [question, setQuestion] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [humanResponse, setHumanResponse] = useState('');
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'input' | 'ai-response' | 'comparison' | 'results'>('input');
  const [copySuccess, setCopySuccess] = useState(false);
  const [copiedAI, setCopiedAI] = useState(false);
  const [copiedHuman, setCopiedHuman] = useState(false);
  const [copiedAIMain, setCopiedAIMain] = useState(false);
  const [streamingResponse, setStreamingResponse] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [evaluationLogs, setEvaluationLogs] = useState<string[]>([]);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const aiResponseRef = useRef<HTMLDivElement>(null);
  const [isQuestionCollapsed, setIsQuestionCollapsed] = useState(false);

// ...existing code...

  const parseEmailAndGenerateResponse = async () => {
    if (!emailContent.trim()) {
      setError('Please paste an email to parse');
      return;
    }

    setLoading(true);
    setError(null);
    setStep('ai-response');
    setStreamingResponse('');
    setIsStreaming(true);

    // Collapse the question and scroll to AI response section
    setTimeout(() => {
      setIsQuestionCollapsed(true);
      aiResponseRef.current?.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start' 
      });
    }, 100);

    try {
      // First, parse the email
      const parseResponse = await fetch('/api/parse-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email_text: emailContent }),
      });

      if (!parseResponse.ok) {
        throw new Error('Failed to parse email');
      }

      const parseData = await parseResponse.json();
      setQuestion(parseData.question);
      setContext(parseData.context);

      // Then, generate AI response with streaming
      const response = await fetch('/api/generate-response', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: parseData.question,
          context: parseData.context,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate AI response');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.content) {
                  fullResponse += data.content;
                  setStreamingResponse(fullResponse);
                }
                if (data.status === 'complete') {
                  setAiResponse(fullResponse);
                  setIsStreaming(false);
                }
                if (data.error) {
                  throw new Error(data.error);
                }
              } catch (e) {
                // Ignore JSON parse errors for malformed chunks
              }
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process request');
      setStep('input');
    } finally {
      setLoading(false);
    }
  };

  const runComparison = async () => {
    if (!question.trim() || !humanResponse.trim() || !aiResponse.trim()) {
      setError('Missing required data for comparison');
      return;
    }

    setLoading(true);
    setIsEvaluating(true);
    setError(null);
    setEvaluationLogs([]);
    setStep('results');

    // Add progress logs
    const addLog = (message: string) => {
      setEvaluationLogs(prev => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
    };

    try {
      addLog('Starting evaluation process...');
      addLog('Preparing responses for comparison...');
      
      // Add some simulated progress logs
      setTimeout(() => addLog('Analyzing response quality...'), 500);
      setTimeout(() => addLog('Calculating technical accuracy scores...'), 1000);
      setTimeout(() => addLog('Evaluating completeness and clarity...'), 1500);
      setTimeout(() => addLog('Assessing professional tone and citations...'), 2000);
      setTimeout(() => addLog('Generating detailed analysis...'), 2500);

      const response = await fetch('/api/evaluate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: question,
          human_response: humanResponse,
          context: context,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to evaluate responses');
      }

      addLog('Finalizing evaluation results...');
      const data = await response.json();
      addLog('Evaluation complete!');
      
      setTimeout(() => {
        setResult(data);
        setIsEvaluating(false);
      }, 500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to evaluate responses');
      setStep('comparison');
      setIsEvaluating(false);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, type: 'ai' | 'human' | 'ai-main') => {
    try {
      await navigator.clipboard.writeText(text);
      if (type === 'ai') {
        setCopiedAI(true);
        setTimeout(() => setCopiedAI(false), 2000);
      } else if (type === 'human') {
        setCopiedHuman(true);
        setTimeout(() => setCopiedHuman(false), 2000);
      } else if (type === 'ai-main') {
        setCopiedAIMain(true);
        setTimeout(() => setCopiedAIMain(false), 2000);
      }
    } catch (err) {
      setError('Failed to copy to clipboard');
    }
  };

  const resetForm = () => {
    setEmailContent('');
    setQuestion('');
    setAiResponse('');
    setHumanResponse('');
    setContext('');
    setResult(null);
    setError(null);
    setStep('input');
    setCopySuccess(false);
    setEvaluationLogs([]);  // Add this line
    setIsEvaluating(false);
  };

  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600';
    if (score >= 6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getWinnerColor = (winner: string) => {
    return winner === 'AI' ? 'text-blue-600' : 'text-purple-600';
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
                <Mail className="h-10 w-10 text-blue-600 mr-3" />
                <h1 className="text-4xl font-bold text-gray-900">Email Support Agent</h1>
              </div>
              <div className="w-32"></div> {/* Spacer for center alignment */}
            </div>
            <p className="text-center text-lg text-gray-600">
              AI-powered email support response generator
            </p>
          </div>

          {/* Progress Steps - Now Clickable */}
          <div className="flex justify-center mb-8">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setStep('input')}
                disabled={loading}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === 'input' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                } disabled:opacity-50`}
              >
                <Mail className="h-5 w-5 mr-2" />
                <span className="font-medium">Email Input</span>
              </button>
              
              <button
                onClick={() => setStep('ai-response')}
                disabled={loading || !aiResponse}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === 'ai-response' 
                    ? 'bg-blue-600 text-white' 
                    : aiResponse 
                      ? 'bg-gray-200 text-gray-600 hover:bg-gray-300' 
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                } disabled:opacity-50`}
              >
                <Brain className="h-5 w-5 mr-2" />
                <span className="font-medium">AI Response</span>
              </button>
              
              <button
                onClick={() => setStep('comparison')}
                disabled={loading || !aiResponse}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === 'comparison' 
                    ? 'bg-blue-600 text-white' 
                    : aiResponse 
                      ? 'bg-gray-200 text-gray-600 hover:bg-gray-300' 
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                } disabled:opacity-50`}
              >
                <Zap className="h-5 w-5 mr-2" />
                <span className="font-medium">Compare (Optional)</span>
              </button>
              
              <button
                onClick={() => setStep('results')}
                disabled={loading || !result}
                className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                  step === 'results' 
                    ? 'bg-blue-600 text-white' 
                    : result 
                      ? 'bg-gray-200 text-gray-600 hover:bg-gray-300' 
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                } disabled:opacity-50`}
              >
                <Trophy className="h-5 w-5 mr-2" />
                <span className="font-medium">Results</span>
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-center">
                <XCircle className="h-5 w-5 text-red-600 mr-2" />
                <span className="text-red-700">{error}</span>
              </div>
            </div>
          )}

          {/* Step 1: Email Input */}
          {step === 'input' && (
            <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">
                Paste Customer Email
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Customer Email Content
                  </label>
                  <textarea
                    value={emailContent}
                    onChange={(e) => setEmailContent(e.target.value)}
                    placeholder="Paste the customer email here..."
                    className="w-full h-40 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={loading}
                  />
                </div>
                <button
                  onClick={parseEmailAndGenerateResponse}
                  disabled={loading || !emailContent.trim()}
                  className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin h-5 w-5 mr-2" />
                      Generating AI Response...
                    </>
                  ) : (
                    <>
                      <Brain className="h-5 w-5 mr-2" />
                      Generate AI Response
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: AI Response Display */}
          {step === 'ai-response' && (
            <div className="space-y-6">
              {/* Extracted Question */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-bold text-gray-900">Extracted Question</h3>
                  <button
                    onClick={() => setIsQuestionCollapsed(!isQuestionCollapsed)}
                    className="text-blue-600 hover:text-blue-800 flex items-center text-sm"
                  >
                    {isQuestionCollapsed ? (
                      <>
                        <Plus className="h-4 w-4 mr-1" />
                        Show Question
                      </>
                    ) : (
                      <>
                        <XCircle className="h-4 w-4 mr-1" />
                        Hide Question
                      </>
                    )}
                  </button>
                </div>
                {!isQuestionCollapsed && (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-gray-800 whitespace-pre-wrap">{question}</p>
                  </div>
                )}
              </div>

              {/* AI Response with Streaming */}
              <div ref={aiResponseRef} className="bg-white rounded-lg shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-bold text-blue-600">
                    AI Generated Response
                    {isStreaming && (
                      <span className="ml-2 text-sm font-normal text-gray-500">
                        <Loader2 className="inline h-4 w-4 animate-spin mr-1" />
                        Generating...
                      </span>
                    )}
                  </h3>
                  <div className="flex space-x-3">
                    <button
                      onClick={() => copyToClipboard(aiResponse || streamingResponse, 'ai-main')}
                      disabled={!aiResponse && !streamingResponse}
                      className={`px-4 py-2 rounded-lg flex items-center disabled:opacity-50 transition-colors ${
                        copiedAIMain 
                          ? 'bg-green-600 text-white hover:bg-green-700' 
                          : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                    >
                      {copiedAIMain ? (
                        <>
                          <CheckCircle className="h-4 w-4 mr-2" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4 mr-2" />
                          Copy Response
                        </>
                      )}
                    </button>
                    <button
                      onClick={resetForm}
                      className="bg-gray-600 text-white px-3 py-2 rounded-lg hover:bg-gray-700 text-sm"
                    >
                      New Email
                    </button>
                    <button
                      onClick={() => setStep('comparison')}
                      disabled={!aiResponse}
                      className="bg-green-600 text-white px-3 py-2 rounded-lg hover:bg-green-700 flex items-center disabled:opacity-50 text-sm"
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Compare
                    </button>
                  </div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4 mb-4 min-h-[200px]">
                  <p className="text-blue-900 whitespace-pre-wrap">
                    {isStreaming ? streamingResponse : aiResponse}
                    {isStreaming && <span className="animate-pulse">▊</span>}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Comparison Setup */}
          {step === 'comparison' && (
            <div className="space-y-6">
              {/* AI Response Summary */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-bold text-blue-600 mb-2">AI Response (Generated)</h3>
                <div className="bg-blue-50 rounded-lg p-3">
                  <p className="text-sm text-blue-900 line-clamp-3">{aiResponse.substring(0, 200)}...</p>
                </div>
              </div>

              {/* Human Response Input */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">Add Human Response for Comparison</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Human Response
                    </label>
                    <textarea
                      value={humanResponse}
                      onChange={(e) => setHumanResponse(e.target.value)}
                      placeholder="Paste the human response here..."
                      className="w-full h-40 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      disabled={loading}
                    />
                  </div>
                  <div className="flex space-x-4">
                    <button
                      onClick={() => setStep('ai-response')}
                      className="flex-1 bg-gray-600 text-white py-3 px-4 rounded-lg hover:bg-gray-700"
                    >
                      Back to AI Response
                    </button>
                    <button
                      onClick={runComparison}
                      disabled={loading || !humanResponse.trim()}
                      className="flex-1 bg-purple-600 text-white py-3 px-4 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="animate-spin h-5 w-5 mr-2" />
                          Comparing Responses...
                        </>
                      ) : (
                        <>
                          <Zap className="h-5 w-5 mr-2" />
                          Run Comparison
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Enhanced Results with All Details */}
          {/* {step === 'results' && result && ( */}
          {step === 'results' && (
            <>
              {/* Evaluation Loading Screen */}
              {isEvaluating && (
                <div className="space-y-6">
                  <div className="bg-white rounded-lg shadow-lg p-8">
                    <div className="text-center mb-6">
                      <div className="flex items-center justify-center mb-4">
                        <Loader2 className="h-12 w-12 text-blue-600 animate-spin mr-4" />
                        <div>
                          <h2 className="text-2xl font-bold text-gray-900">Evaluating Responses</h2>
                          <p className="text-gray-600">AI is analyzing and comparing the responses...</p>
                        </div>
                      </div>
                      
                      {/* Progress Bar */}
                      <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
                        <div 
                          className="bg-blue-600 h-2 rounded-full transition-all duration-1000 ease-out"
                          style={{ width: `${Math.min((evaluationLogs.length / 7) * 100, 100)}%` }}
                        ></div>
                      </div>
                    </div>

                    {/* Live Logs */}
                    <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
                      <h3 className="font-semibold text-gray-900 mb-3 flex items-center">
                        <MessageSquare className="h-5 w-5 mr-2" />
                        Evaluation Progress
                      </h3>
                      <div className="space-y-2">
                        {evaluationLogs.map((log, index) => (
                          <div 
                            key={index}
                            className="flex items-start animate-fade-in"
                            style={{ 
                              animationDelay: `${index * 0.1}s`,
                              animationFillMode: 'both'
                            }}
                          >
                            <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                            <p className="text-sm text-gray-700 font-mono">{log}</p>
                          </div>
                        ))}
                        {evaluationLogs.length > 0 && (
                          <div className="flex items-center mt-2">
                            <Loader2 className="h-4 w-4 text-blue-600 animate-spin mr-2" />
                            <span className="text-sm text-blue-600">Processing...</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Actual Results - Only show when evaluation is complete */}
              {!isEvaluating && result && (
            <div className="space-y-6">
              {/* Quick Response Access */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold text-blue-600">AI Response</h3>
                    <button
                      onClick={() => copyToClipboard(result.ai_response, 'ai')}
                      className={`px-4 py-2 rounded-lg flex items-center transition-colors ${
                        copiedAI 
                          ? 'bg-green-600 text-white hover:bg-green-700' 
                          : 'bg-blue-600 text-white hover:bg-blue-700'
                      }`}
                    >
                      {copiedAI ? (
                        <>
                          <CheckCircle className="h-4 w-4 mr-2" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4 mr-2" />
                          Copy
                        </>
                      )}
                    </button>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4 max-h-64 overflow-y-auto">
                    <p className="text-sm text-blue-900 whitespace-pre-wrap">
                      {result.ai_response}
                    </p>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold text-purple-600">Human Response</h3>
                    <button
                      onClick={() => copyToClipboard(result.human_response, 'human')}
                      className={`px-4 py-2 rounded-lg flex items-center transition-colors ${
                        copiedHuman 
                          ? 'bg-green-600 text-white hover:bg-green-700' 
                          : 'bg-purple-600 text-white hover:bg-purple-700'
                      }`}
                    >
                      {copiedHuman ? (
                        <>
                          <CheckCircle className="h-4 w-4 mr-2" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4 mr-2" />
                          Copy
                        </>
                      )}
                    </button>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4 max-h-64 overflow-y-auto">
                    <p className="text-sm text-purple-900 whitespace-pre-wrap">
                      {result.human_response}
                    </p>
                  </div>
                </div>
              </div>

              {/* Winner Card */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="text-center">
                  <Trophy className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
                  <h2 className="text-3xl font-bold text-gray-900 mb-2">
                    Winner: <span className={getWinnerColor(result.winner)}>{result.winner}</span>
                  </h2>
                  <p className="text-lg text-gray-600">
                    {result.evaluation.overall_reasoning}
                  </p>
                </div>
              </div>

              {/* Detailed Scores Comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* AI Response Scores - Always on the left */}
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-xl font-bold text-blue-600 mb-4">
                    AI Response Scores (Generated)
                  </h3>
                  <div className="space-y-3">
                    {Object.entries(
                      result.labels.response_a === 'AI' 
                        ? result.evaluation.scores.response_a 
                        : result.evaluation.scores.response_b
                    ).map(([key, value]) => {
                      if (key === 'total') return null;
                      return (
                        <div key={key} className="flex justify-between items-center">
                          <span className="capitalize text-sm text-gray-600">
                            {key.replace('_', ' ')}
                          </span>
                          <span className={`font-bold ${getScoreColor(Number(value))}`}>
                            {value}/10
                          </span>
                        </div>
                      );
                    })}
                    <div className="border-t pt-3">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-gray-900">Total</span>
                        <span className="font-bold text-lg text-blue-600">
                          {result.labels.response_a === 'AI' 
                            ? result.evaluation.scores.response_a.total 
                            : result.evaluation.scores.response_b.total}/60
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Human Response Scores - Always on the right */}
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-xl font-bold text-purple-600 mb-4">
                    Human Response Scores (Manual)
                  </h3>
                  <div className="space-y-3">
                    {Object.entries(
                      result.labels.response_a === 'Human' 
                        ? result.evaluation.scores.response_a 
                        : result.evaluation.scores.response_b
                    ).map(([key, value]) => {
                      if (key === 'total') return null;
                      return (
                        <div key={key} className="flex justify-between items-center">
                          <span className="capitalize text-sm text-gray-600">
                            {key.replace('_', ' ')}
                          </span>
                          <span className={`font-bold ${getScoreColor(Number(value))}`}>
                            {value}/10
                          </span>
                        </div>
                      );
                    })}
                    <div className="border-t pt-3">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-gray-900">Total</span>
                        <span className="font-bold text-lg text-purple-600">
                          {result.labels.response_a === 'Human' 
                            ? result.evaluation.scores.response_a.total 
                            : result.evaluation.scores.response_b.total}/60
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Detailed Analysis */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-xl font-bold text-blue-600 mb-4">
                    {result.labels.response_a} Response Analysis
                    <span className="text-sm font-normal text-gray-500 ml-2">
                      ({result.labels.response_a === 'AI' ? 'Generated' : 'Human'})
                    </span>
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-semibold text-green-600 mb-2 flex items-center">
                        <CheckCircle className="h-5 w-5 mr-2" />
                        Strengths:
                      </h4>
                      <ul className="text-sm text-gray-600 space-y-2">
                        {result.evaluation.detailed_analysis.response_a_strengths.map((strength, idx) => (
                          <li key={idx} className="flex items-start">
                            <div className="w-2 h-2 bg-green-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                            {strength}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <h4 className="font-semibold text-red-600 mb-2 flex items-center">
                        <XCircle className="h-5 w-5 mr-2" />
                        Weaknesses:
                      </h4>
                      <ul className="text-sm text-gray-600 space-y-2">
                        {result.evaluation.detailed_analysis.response_a_weaknesses.map((weakness, idx) => (
                          <li key={idx} className="flex items-start">
                            <div className="w-2 h-2 bg-red-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                            {weakness}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="bg-blue-50 rounded-lg p-4">
                      <h4 className="font-semibold text-blue-800 mb-2">Detailed Feedback:</h4>
                      <p className="text-sm text-blue-700">
                        {result.evaluation.specific_feedback.response_a}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-xl font-bold text-purple-600 mb-4">
                    {result.labels.response_b} Response Analysis
                    <span className="text-sm font-normal text-gray-500 ml-2">
                      ({result.labels.response_b === 'AI' ? 'Generated' : 'Human'})
                    </span>
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-semibold text-green-600 mb-2 flex items-center">
                        <CheckCircle className="h-5 w-5 mr-2" />
                        Strengths:
                      </h4>
                      <ul className="text-sm text-gray-600 space-y-2">
                        {result.evaluation.detailed_analysis.response_b_strengths.map((strength, idx) => (
                          <li key={idx} className="flex items-start">
                            <div className="w-2 h-2 bg-green-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                            {strength}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <h4 className="font-semibold text-red-600 mb-2 flex items-center">
                        <XCircle className="h-5 w-5 mr-2" />
                        Weaknesses:
                      </h4>
                      <ul className="text-sm text-gray-600 space-y-2">
                        {result.evaluation.detailed_analysis.response_b_weaknesses.map((weakness, idx) => (
                          <li key={idx} className="flex items-start">
                            <div className="w-2 h-2 bg-red-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                            {weakness}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-4">
                      <h4 className="font-semibold text-purple-800 mb-2">Detailed Feedback:</h4>
                      <p className="text-sm text-purple-700">
                        {result.evaluation.specific_feedback.response_b}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Evaluation Metadata */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Evaluation Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">Evaluation ID:</span>
                    <p className="text-xs font-mono bg-gray-100 px-2 py-1 rounded mt-1">{result.evaluation_id}</p>
                  </div>
                  <div>
                    <span className="font-medium">Timestamp:</span>
                    <p className="mt-1">{new Date(result.timestamp).toLocaleString()}</p>
                  </div>
                  <div>
                    <span className="font-medium">Response Labels:</span>
                    <p className="mt-1">A: {result.labels.response_a}, B: {result.labels.response_b}</p>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="text-center">
                <button
                  onClick={resetForm}
                  className="bg-blue-600 text-white py-3 px-8 rounded-lg hover:bg-blue-700 font-medium"
                >
                  Process Another Email
                </button>
              </div>
                        </div>
              )}
            </>
          )}
        </div>
      </div>
      
    </div>
  );
}

export default EmailSupportAgent;