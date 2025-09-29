import React, { useState } from 'react';
// @ts-ignore
import ReactMarkdown from 'react-markdown';
// @ts-ignore
import remarkGfm from 'remark-gfm';
import { WordExporter } from '../utils/wordExporter';
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

interface Section {
  section_id: string;
  title: string;
  content: string;
  order: number;
  status: 'pending' | 'generating' | 'complete' | 'editing';
  editContent?: string;
}

interface ReviewComment {
  section: string;
  comment: string;
  suggestion: string;
  line_number?: number;
}

const preprocessMarkdown = (content: string): string => {
  const lines = content.split('\n');
  const processedLines: string[] = [];
  let inTable = false;
  let tableBuffer: string[][] = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmedLine = line.trim();
    
    // Check if this looks like a table row
    if (trimmedLine.includes('|') && !trimmedLine.match(/^\s*$/) && trimmedLine !== '|') {
      // Parse cells
      let cells = trimmedLine
        .split('|')
        .map(cell => cell.trim())
        .filter((cell, index, arr) => {
          // Keep cells that aren't empty, unless they're at the edges
          return !(index === 0 || index === arr.length - 1) || cell !== '';
        });
      
      // Remove empty edge cells if they exist
      if (cells[0] === '') cells.shift();
      if (cells[cells.length - 1] === '') cells.pop();
      
      // Skip separator rows
      if (cells.every(cell => cell.match(/^[\-\s:]+$/))) {
        if (tableBuffer.length === 1) {
          // This is the separator after headers, add it
          processedLines.push('| ' + tableBuffer[0].join(' | ') + ' |');
          processedLines.push('|' + cells.map(() => ' --- ').join('|') + '|');
          tableBuffer = [];
          inTable = true;
        }
        continue;
      }
      
      // Process each cell to handle inline markdown
      cells = cells.map(cell => {
        return cell
          // Convert <br> tags to actual line breaks for markdown
          .replace(/<br\s*\/?>/gi, '  \n')
          // Handle bold text
          .replace(/\*\*(.*?)\*\*/g, '**$1**')
          // Handle lists
          .replace(/^\s*[-•]\s+/gm, '• ')
          // Clean up quotes
          .replace(/[""]/g, '"')
          .replace(/['']/g, "'");
      });
      
      if (!inTable) {
        // Start collecting table rows
        tableBuffer.push(cells);
      } else {
        // Output the row directly
        processedLines.push('| ' + cells.join(' | ') + ' |');
      }
    } else {
      // Not a table line
      if (tableBuffer.length > 0) {
        // Output any buffered table content
        if (tableBuffer.length === 1) {
          // Single row, treat as headers
          processedLines.push('| ' + tableBuffer[0].join(' | ') + ' |');
          processedLines.push('|' + tableBuffer[0].map(() => ' --- ').join('|') + '|');
        } else {
          // Multiple rows
          processedLines.push('| ' + tableBuffer[0].join(' | ') + ' |');
          processedLines.push('|' + tableBuffer[0].map(() => ' --- ').join('|') + '|');
          for (let j = 1; j < tableBuffer.length; j++) {
            processedLines.push('| ' + tableBuffer[j].join(' | ') + ' |');
          }
        }
        tableBuffer = [];
      }
      
      inTable = false;
      
      // Process other markdown elements
      let processedLine = line
        .replace(/<br\s*\/?>/gi, '  \n')
        .replace(/<ul>/gi, '')
        .replace(/<\/ul>/gi, '')
        .replace(/<li>/gi, '• ')
        .replace(/<\/li>/gi, '')
        .replace(/^\*\s+/gm, '• ')
        .replace(/<[^>]*>/g, '');
      
      processedLines.push(processedLine);
    }
  }
  
  // Handle any remaining buffered table content
  if (tableBuffer.length > 0) {
    if (tableBuffer.length === 1) {
      processedLines.push('| ' + tableBuffer[0].join(' | ') + ' |');
      processedLines.push('|' + tableBuffer[0].map(() => ' --- ').join('|') + '|');
    } else {
      processedLines.push('| ' + tableBuffer[0].join(' | ') + ' |');
      processedLines.push('|' + tableBuffer[0].map(() => ' --- ').join('|') + '|');
      for (let j = 1; j < tableBuffer.length; j++) {
        processedLines.push('| ' + tableBuffer[j].join(' | ') + ' |');
      }
    }
  }
  
  return processedLines
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/^(#{1,3}\s+.+)$/gm, '\n$1\n')
    .trim();
};


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
  const [sections, setSections] = useState<Section[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [generationMode, setGenerationMode] = useState<'auto' | 'manual'>('auto'); // Add this
  const [waitingForApproval, setWaitingForApproval] = useState(false); // Add this
  const [reviewComments, setReviewComments] = useState<ReviewComment[]>([]);
  const [reviewResult, setReviewResult] = useState<any>(null);
  const [isStreamingReview, setIsStreamingReview] = useState(false);
  const [streamingReviewContent, setStreamingReviewContent] = useState('');
  const [parsedComments, setParsedComments] = useState<Array<{section: string, comment: string, lineRef: string}>>([]);


  // const createPRD = async () => {
  //   if (!prompt.trim()) {
  //     setError('Please enter a description for your PRD');
  //     return;
  //   }

  //   setLoading(true);
  //   setError(null);

  //   try {
  //     // Prepare context from data sources
  //     const contextData = dataSources.map(ds => ({
  //       type: ds.type,
  //       name: ds.name,
  //       content: ds.content
  //     }));

  //     const response = await fetch('/api/prd/create', {
  //       method: 'POST',
  //       headers: {
  //         'Content-Type': 'application/json',
  //       },
  //       body: JSON.stringify({
  //         prompt: prompt,
  //         context: 'AKS PRD creation',
  //         data_sources: contextData
  //       }),
  //     });

  //     if (!response.ok) {
  //       const errorData = await response.json();
  //       throw new Error(errorData.error || 'Failed to create PRD');
  //     }

  //     const data = await response.json();
  //     setResult(data);
  //     setStep('create');
  //   } catch (err) {
  //     setError(err instanceof Error ? err.message : 'Failed to create PRD');
  //   } finally {
  //     setLoading(false);
  //   }
  // };
  const createPRD = async () => {
    if (!prompt.trim()) {
      setError('Please enter a description for your PRD');
      return;
    }

    setLoading(true);
    setError(null);
    setSections([]);
    setIsStreaming(true);
    setCurrentSectionIndex(0);  // Add this
    setWaitingForApproval(false);  // Add this

    try {
      const contextData = dataSources.map(ds => ({
        type: ds.type,
        name: ds.name,
        content: ds.content
      }));

      const response = await fetch('/api/prd/create-stream', {
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
        throw new Error('Failed to create PRD');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'section') {
                setSections(prev => {
                  const newSections = [...prev];
                  const existingIndex = newSections.findIndex(s => s.section_id === data.section_id);
                  
                  if (existingIndex >= 0) {
                    newSections[existingIndex] = {
                      ...data,
                      status: 'complete'
                    };
                  } else {
                    newSections.push({
                      ...data,
                      status: 'complete'
                    });
                  }
                  
                  return newSections;
                });
                
                setCurrentSectionIndex(prev => prev + 1);
                
                // If in manual mode, pause after each section
                if (generationMode === 'manual') {
                  setWaitingForApproval(true);
                  setIsStreaming(false);
                  // Close the reader to stop the stream
                  reader.cancel();
                  return; // Exit the function
                }
              } else if (data.type === 'complete') {
                setIsStreaming(false);
                setStep('create');
              } else if (data.type === 'error') {
                setError(data.error);
                setIsStreaming(false);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create PRD');
      setIsStreaming(false);
    } finally {
      setLoading(false);
    }
  };
  const editSection = (sectionId: string) => {
    setSections(prev => prev.map(s => 
      s.section_id === sectionId 
        ? { ...s, status: 'editing', editContent: s.content }
        : s
    ));
  };

  const saveSection = (sectionId: string) => {
    setSections(prev => prev.map(s => 
      s.section_id === sectionId 
        ? { ...s, status: 'complete', content: s.editContent || s.content, editContent: undefined }
        : s
    ));
  };

  const cancelEdit = (sectionId: string) => {
    setSections(prev => prev.map(s => 
      s.section_id === sectionId 
        ? { ...s, status: 'complete', editContent: undefined }
        : s
    ));
  };
  const continueGeneration = async () => {
    setIsStreaming(true);
    setWaitingForApproval(false);
    
    try {
      // Get all current sections with potentially edited content
      const previousSections = sections.reduce((acc, s) => {
        acc[s.title] = s.content;
        return acc;
      }, {} as {[key: string]: string});
      
      const response = await fetch('/api/prd/continue-generation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          context: 'AKS PRD creation',
          data_sources: dataSources.map(ds => ({
            type: ds.type,
            name: ds.name,
            content: ds.content
          })),
          previous_sections: previousSections,
          start_from_index: currentSectionIndex  // This should be the next section to generate
        })
      });

      if (!response.ok) {
        throw new Error('Failed to continue generation');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let firstSection = true;
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'section') {
                setSections(prev => {
                  const newSections = [...prev];
                  const existingIndex = newSections.findIndex(s => s.section_id === data.section_id);
                  
                  if (existingIndex >= 0) {
                    newSections[existingIndex] = {
                      ...data,
                      status: 'complete'
                    };
                  } else {
                    newSections.push({
                      ...data,
                      status: 'complete'
                    });
                  }
                  
                  return newSections;
                });
                
                setCurrentSectionIndex(prev => prev + 1);
                
                // If in manual mode and this is the first section of this continuation, pause
                if (generationMode === 'manual' && firstSection) {
                  firstSection = false;
                  setWaitingForApproval(true);
                  setIsStreaming(false);
                  reader.cancel();
                  return;
                }
              } else if (data.type === 'complete') {
                setIsStreaming(false);
              } else if (data.type === 'error') {
                setError(data.error);
                setIsStreaming(false);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to continue generation');
      setIsStreaming(false);
    }
  };  
  const reviewPRD = async () => {
    let prdContent = '';
    
    if (reviewMode === 'file' && prdFile) {
      prdContent = await readFileContent(prdFile);
    } else if (reviewMode === 'text' && prdText.trim()) {
      prdContent = prdText;
    } else {
      setError('Please provide PRD content to review');
      return;
    }

    setLoading(false);
    setIsStreamingReview(true);
    setError(null);
    setReviewComments([]);
    setReviewResult(null);
    setStreamingReviewContent('');
    setParsedComments([]);
    setStep('review');

    try {
      const response = await fetch('/api/prd/review-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prd_text: prdContent, context: 'AKS PRD review' }),
      });

      if (!response.ok) throw new Error('Failed to review PRD');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';

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
                  fullContent += data.content;
                  setStreamingReviewContent(fullContent);
                  
                  // Parse comments as they come in
                  const comments = parseCommentsFromContent(fullContent, prdContent);
                  setParsedComments(comments);
                }
                
                if (data.status === 'complete') {
                  setIsStreamingReview(false);
                  setReviewResult({
                    summary: fullContent,
                    comments: parseCommentsFromContent(fullContent, prdContent),
                    score: calculateQuickScore(fullContent)
                  });
                  return; // Exit the function successfully
                }
                
                if (data.error) {
                  throw new Error(data.error);
                }
              } catch (e) {
                // Skip malformed JSON lines
                console.warn('Failed to parse streaming data:', e);
              }
            }
          }
        }
        
        // Fallback if no 'complete' status was received
        setIsStreamingReview(false);
        setReviewResult({
          summary: fullContent,
          comments: parseCommentsFromContent(fullContent, prdContent),
          score: calculateQuickScore(fullContent)
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to review PRD');
      setIsStreamingReview(false);
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

  const calculateQuickScore = (content: string): number => {
    let score = 50;
    if (content.length > 1000) score += 20;
    if (content.includes('requirements')) score += 10;
    if (content.includes('timeline')) score += 10;
    if (content.includes('metrics')) score += 10;
    return Math.min(score, 100);
  };
    
  const parseCommentsFromContent = (content: string, originalPRD: string): Array<{section: string, comment: string, lineRef: string, lineIndex: number}> => {
    const comments: Array<{section: string, comment: string, lineRef: string, lineIndex: number}> = [];
    const lines = originalPRD.split('\n');
    const sections = content.split('**Section:').slice(1);
    
    sections.forEach(section => {
      const [title, ...rest] = section.split('\n');
      const sectionTitle = title.replace(/\*\*/g, '').trim();
      const commentText = rest.join('\n');
      
      // Find line reference in original document
      const lineIndex = lines.findIndex(line => 
        line.toLowerCase().includes(sectionTitle.toLowerCase()) ||
        sectionTitle.toLowerCase().includes(line.toLowerCase().trim())
      );
      
      if (commentText.trim()) {
        comments.push({
          section: sectionTitle,
          comment: commentText.trim(),
          lineRef: lineIndex >= 0 ? `Line ${lineIndex + 1}` : 'General',
          lineIndex: lineIndex >= 0 ? lineIndex : -1
        });
      }
    });
    
    return comments;
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

  const copyToClipboard = (text: string) => {
    // If we have sections (from create mode), use rich formatting
    if (sections && sections.length > 0) {
      const richTextHtml = `
        <html>
          <body style="font-family: 'Aptos Body', 'Calibri', sans-serif; font-size: 11pt; line-height: 1.5;">
            ${sections
              .sort((a, b) => a.order - b.order)
              .map(s => `
                <h2 style="font-family: 'Aptos Display', 'Calibri', sans-serif; font-size: 14pt; color: #2b579a; margin-top: 18pt; margin-bottom: 6pt;">
                  ${s.title}
                </h2>
                <div style="margin-bottom: 12pt;">
                  ${convertMarkdownToHtml(s.content)}
                </div>
              `)
              .join('<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 18pt 0;">')}
          </body>
        </html>
      `;
      
      const blob = new Blob([richTextHtml], { type: 'text/html' });
      const clipboardItem = new ClipboardItem({ 'text/html': blob, 'text/plain': new Blob([text], { type: 'text/plain' }) });
      
      navigator.clipboard.write([clipboardItem]).then(() => {
        alert('PRD copied to clipboard with formatting!');
      }).catch(err => {
        navigator.clipboard.writeText(text);
        alert('PRD copied as plain text');
      });
    } else {
      // Fallback to plain text copy
      navigator.clipboard.writeText(text).then(() => {
        alert('Content copied to clipboard!');
      }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard');
      });
    }
  };

  const fixSectionFormatting = (sectionId: string) => {
    setSections(prev => prev.map(s => {
      if (s.section_id === sectionId) {
        return {
          ...s,
          content: preprocessMarkdown(s.content)
        };
      }
      return s;
    }));
  };

  // Helper function to convert markdown to HTML
  const convertMarkdownToHtml = (markdown: string): string => {
    return markdown
      .replace(/### (.*?)$/gm, '<h3 style="font-size: 12pt; font-weight: bold; margin-top: 12pt; margin-bottom: 6pt;">$1</h3>')
      .replace(/## (.*?)$/gm, '<h2 style="font-size: 13pt; font-weight: bold; margin-top: 12pt; margin-bottom: 6pt;">$1</h2>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.*?)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>\n?)+/g, '<ul style="margin-left: 20pt;">$&</ul>')
      .replace(/\|([^|]+)\|([^|]+)\|/g, '<tr><td style="border: 1px solid #d0d0d0; padding: 6pt;">$1</td><td style="border: 1px solid #d0d0d0; padding: 6pt;">$2</td></tr>')
      .replace(/(<tr>.*<\/tr>\n?)+/g, '<table style="border-collapse: collapse; width: 100%;">$&</table>')
      .replace(/\n/g, '<br/>');
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

              {/* Generation Mode Toggle */}
              <div className="mb-4 p-4 bg-blue-50 rounded-lg">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Generation Mode
                </label>
                <div className="flex space-x-4">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="auto"
                      checked={generationMode === 'auto'}
                      onChange={(e) => setGenerationMode('auto')}
                      className="mr-2"
                    />
                    <span className="text-sm">Auto (Generate all sections continuously)</span>
                  </label>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="manual"
                      checked={generationMode === 'manual'}
                      onChange={(e) => setGenerationMode('manual')}
                      className="mr-2"
                    />
                    <span className="text-sm">Manual (Review each section before continuing)</span>
                  </label>
                </div>
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

              {/* PRD Result with Sections */}
              {sections.length > 0 && (
                <div className="mt-8 border-t pt-8">
                  <div className="flex items-center justify-between mb-6">
                    <h4 className="text-xl font-bold text-green-700">
                      {isStreaming ? '⏳ Generating PRD...' : '✅ PRD Created Successfully!'}
                    </h4>
                    {!isStreaming && (
                      <div className="flex space-x-3">
                        <button
                          onClick={() => {
                            const fullPrd = sections
                              .sort((a, b) => a.order - b.order)
                              .map(s => `## ${s.title}\n\n${s.content}`)
                              .join('\n\n---\n\n');
                            navigator.clipboard.writeText(fullPrd).then(() => {
                              alert('PRD copied to clipboard!');
                            });
                          }}
                          className="flex items-center px-4 py-2 text-blue-600 hover:text-blue-800 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
                        >
                          <Copy className="h-4 w-4 mr-2" />
                          Copy as Text
                        </button>
                        <button
                          onClick={() => {
                            WordExporter.exportToWord(sections, prompt || 'Product Requirements Document');
                          }}
                          className="flex items-center px-4 py-2 text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
                        >
                          <FileText className="h-4 w-4 mr-2" />
                          Export to Word
                        </button>
                      </div>
                    )}
                  </div>
                  
                  {/* Progress indicator */}
                  {isStreaming && (
                    <div className="mb-4">
                      <div className="flex space-x-2">
                        {Array.from({ length: 15 }).map((_, i) => (  // Change 5 to 15 for all sections
                          <div
                            key={i}
                            className={`h-2 flex-1 rounded ${
                              i < currentSectionIndex ? 'bg-green-500' : 'bg-gray-300'
                            }`}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Sections */}
                  <div className="space-y-4">
                    {sections.map((section) => (
                      <div key={section.section_id} className="bg-gray-50 rounded-lg p-6">
                        <div className="flex items-center justify-between mb-3">
                          <h5 className="text-lg font-semibold">{section.title}</h5>
                        </div>
                        
                        {section.status === 'editing' ? (
                          <div>
                            <textarea
                              value={section.editContent}
                              onChange={(e) => {
                                setSections(prev => prev.map(s => 
                                  s.section_id === section.section_id 
                                    ? { ...s, editContent: e.target.value }
                                    : s
                                ));
                              }}
                              className="w-full p-3 border rounded-lg mb-2"
                              rows={8}
                            />
                            <div className="flex space-x-2">
                              <button
                                onClick={() => saveSection(section.section_id)}
                                className="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => cancelEdit(section.section_id)}
                                className="px-3 py-1 bg-gray-500 text-white rounded hover:bg-gray-600"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                          ) : (
                            <div className="prose max-w-none">
                              <ReactMarkdown 
                                remarkPlugins={[remarkGfm]} // Add this if you haven't already imported it
                                components={{
                                  table: ({ children }) => (
                                    <div className="overflow-x-auto my-4">
                                      <table className="min-w-full border-collapse border border-gray-300">
                                        {children}
                                      </table>
                                    </div>
                                  ),
                                  a: ({ href, children }) => {
                                    // Fix any placeholder URLs
                                    if (!href || href === 'internal' || href?.includes('localhost')) {
                                        // Default to AKS docs for wiki citations
                                        if (children?.toString().includes('Wiki')) {
                                            href = 'https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki';
                                        } else {
                                            href = 'https://learn.microsoft.com/en-us/azure/aks/';
                                        }
                                    }
                                    return (
                                        <a 
                                            href={href} 
                                            target="_blank" 
                                            rel="noopener noreferrer"
                                            className="text-blue-600 hover:text-blue-800 underline"
                                        >
                                            {children}
                                        </a>
                                    );
                                },
                                  thead: ({ children }) => (
                                    <thead className="bg-gray-100">{children}</thead>
                                  ),
                                  tbody: ({ children }) => (
                                    <tbody className="divide-y divide-gray-200">{children}</tbody>
                                  ),
                                  tr: ({ children }) => (
                                    <tr className="hover:bg-gray-50">{children}</tr>
                                  ),
                                  th: ({ children }) => (
                                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900 border border-gray-300">
                                      {children}
                                    </th>
                                  ),
                                  td: ({ children }) => (
                                    <td className="px-4 py-3 text-sm text-gray-700 border border-gray-300 whitespace-pre-wrap">
                                      {children}
                                    </td>
                                  ),
                                  p: ({ children }) => (
                                    <p className="mb-2">{children}</p>
                                  ),
                                  ul: ({ children }) => (
                                    <ul className="list-disc pl-5 space-y-1">{children}</ul>
                                  ),
                                  li: ({ children }) => (
                                    <li className="text-sm">{children}</li>
                                  ),
                                  strong: ({ children }) => (
                                    <strong className="font-semibold text-gray-900">{children}</strong>
                                  ),
                                  br: () => <br />
                                }}
                              >
                                {section.content}
                              </ReactMarkdown>
                            </div>
                          )}
                          {/* ADD IT HERE - Right after the ternary operator closes */}
                          {waitingForApproval && section.order === currentSectionIndex && (
                            <div className="mt-6 border-t pt-4">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center space-x-2">
                                  <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></div>
                                  <span className="text-sm font-medium text-gray-700">Section generated successfully</span>
                                </div>
                                <div className="flex items-center space-x-3">
                                  <button
                                    onClick={() => editSection(section.section_id)}
                                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                  >
                                    <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                    </svg>
                                    Edit Section
                                  </button>
                                  <button
                                    onClick={() => {
                                      setWaitingForApproval(false);
                                      continueGeneration();
                                    }}
                                    className="inline-flex items-center px-4 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                  >
                                    Continue to Next Section
                                    <svg className="w-4 h-4 ml-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                  </button>
                                </div>
                              </div>
                            </div>
                          )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Review PRD Input */}
          {step === 'review' && mode === 'review' && !reviewResult && (
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

              <p className="text-gray-600 mb-6">
                Paste your PRD content or upload a file to get AI-powered feedback and suggestions for improvement.
              </p>

              {/* Review Mode Toggle */}
              <div className="mb-6">
                <div className="flex space-x-4 mb-4">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="text"
                      checked={reviewMode === 'text'}
                      onChange={(e) => setReviewMode('text')}
                      className="mr-2"
                    />
                    <span className="text-sm font-medium">Paste Text</span>
                  </label>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="radio"
                      value="file"
                      checked={reviewMode === 'file'}
                      onChange={(e) => setReviewMode('file')}
                      className="mr-2"
                    />
                    <span className="text-sm font-medium">Upload File</span>
                  </label>
                </div>
              </div>

              {/* Text Input Mode */}
              {reviewMode === 'text' && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    PRD Content
                  </label>
                  <textarea
                    value={prdText}
                    onChange={(e) => setPrdText(e.target.value)}
                    placeholder="Paste your PRD content here..."
                    className="w-full h-64 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              )}

              {/* File Upload Mode */}
              {reviewMode === 'file' && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Upload PRD File
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                    <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600 mb-4">
                      Upload your PRD document (.txt, .doc, .docx, .md)
                    </p>
                    <input
                      type="file"
                      accept=".txt,.doc,.docx,.pdf,.md"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setPrdFile(file);
                        }
                      }}
                      className="hidden"
                      id="prd-file-upload"
                    />
                    <label
                      htmlFor="prd-file-upload"
                      className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
                    >
                      Choose File
                    </label>
                    {prdFile && (
                      <p className="mt-2 text-sm text-green-600">
                        Selected: {prdFile.name}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-red-700">{error}</p>
                </div>
              )}

              {/* Review Button */}
              <button
                onClick={reviewPRD}
                disabled={loading || isStreamingReview || (!prdText.trim() && !prdFile)}
                className="w-full flex items-center justify-center px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isStreamingReview ? (
                  <>
                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                    Analyzing PRD...
                  </>
                ) : (
                  <>
                    <MessageSquare className="h-5 w-5 mr-2" />
                    Review PRD
                  </>
                )}
              </button>
            </div>
          )}
          {/* Review Results */}
          {step === 'review' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-7xl mx-auto">
              {/* Document Panel */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-800 flex items-center">
                    <FileText className="w-5 h-5 mr-2" />
                    Document
                  </h3>
                  <button
                    onClick={() => setStep('select')}
                    className="flex items-center px-3 py-1 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm"
                  >
                    <ArrowLeft className="w-4 h-4 mr-1" />
                    Back
                  </button>
                </div>
                <div className="bg-gray-50 rounded-lg p-4 max-h-[600px] overflow-y-auto border">
                  <div className="prose prose-sm max-w-none text-gray-800 leading-relaxed">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                    >
                      {reviewMode === 'text' ? prdText : prdFile ? 'File uploaded for review' : 'No content provided'}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>

              {/* Comments Panel */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-800 flex items-center">
                    <MessageSquare className="w-5 h-5 mr-2" />
                    Review Comments
                    {isStreamingReview && (
                      <Loader2 className="w-4 h-4 ml-2 animate-spin text-blue-600" />
                    )}
                  </h3>
                  {streamingReviewContent && (
                    <button
                      onClick={() => copyToClipboard(streamingReviewContent)}
                      className="flex items-center px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 text-sm"
                    >
                      <Copy className="w-4 h-4 mr-1" />
                      Copy
                    </button>
                  )}
                </div>
                <div className="bg-blue-50 rounded-lg p-4 max-h-[600px] overflow-y-auto border border-blue-200">
                  {isStreamingReview && !streamingReviewContent && (
                    <div className="flex items-center text-blue-600">
                      <Loader2 className="w-4 w-4 mr-2 animate-spin" />
                      <span className="text-sm">Starting review analysis...</span>
                    </div>
                  )}
                  {streamingReviewContent && (
                    <div className="prose prose-sm max-w-none text-gray-800 leading-relaxed">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({children}) => <h1 className="text-xl font-bold text-blue-800 mb-3">{children}</h1>,
                          h2: ({children}) => <h2 className="text-lg font-semibold text-blue-700 mb-2 mt-4">{children}</h2>,
                          h3: ({children}) => <h3 className="text-base font-medium text-blue-600 mb-2 mt-3">{children}</h3>,
                          strong: ({children}) => <strong className="font-semibold text-gray-900">{children}</strong>,
                          p: ({children}) => <p className="mb-3 text-gray-700 leading-relaxed">{children}</p>,
                          ul: ({children}) => <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>,
                          li: ({children}) => <li className="text-gray-700">{children}</li>
                        }}
                      >
                        {streamingReviewContent}
                      </ReactMarkdown>
                    </div>
                  )}
                  {!isStreamingReview && !streamingReviewContent && !reviewResult && (
                    <p className="text-gray-500 text-center py-8">Review will appear here...</p>
                  )}
                </div>
                
                {/* Action Buttons */}
                {streamingReviewContent && !isStreamingReview && (
                  <div className="flex space-x-3 mt-4">
                    <button
                      onClick={resetForm}
                      className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Review Another PRD
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PRDAgent;