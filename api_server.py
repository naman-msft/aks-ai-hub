from flask_cors import CORS
import os
from ai_grader import AIResponseGrader, AKSResponseTester
from aks import AKSWikiAssistant
import json
import traceback
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
CORS(app)

# Initialize components
assistant = None
grader = None
tester = None

def initialize_components():
    global assistant, grader, tester
    try:
        print("🚀 Initializing AKS Assistant...")
        assistant = AKSWikiAssistant()
        grader = AIResponseGrader()
        tester = AKSResponseTester(assistant, grader)
        
        # Load existing vector store and assistant
        if os.path.exists("vector_store_id.json"):
            with open("vector_store_id.json", 'r') as f:
                assistant.vector_store_id = json.load(f)["vector_store_id"]
        
        if os.path.exists("assistant_id.json"):
            with open("assistant_id.json", 'r') as f:
                assistant.assistant_id = json.load(f)["assistant_id"]
        
        print("✅ Components initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Error initializing components: {e}")
        return False

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "AKS Grader API is running"})

@app.route('/api/evaluate', methods=['POST'])
def evaluate_response():
    try:
        data = request.json
        question = data.get('question', '')
        human_response = data.get('human_response', '')
        context = data.get('context', '')
        
        if not question or not human_response:
            return jsonify({"error": "Question and human response are required"}), 400
        
        # Test the response quality
        print(f"🧪 Processing evaluation request...")
        evaluation = tester.test_response_quality(
            question=question,
            human_response=human_response,
            context=context,
            label_responses=True
        )
        
        if "error" in evaluation:
            return jsonify({"error": evaluation["error"]}), 500
        
        # Format response for frontend
        response = {
            "evaluation_id": evaluation["evaluation_id"],
            "question": question,
            "ai_response": evaluation["responses"]["response_a"] if evaluation["response_labels"]["response_a"] == "AI" else evaluation["responses"]["response_b"],
            "human_response": human_response,
            "evaluation": evaluation["evaluation"],
            "labels": evaluation["response_labels"],
            "winner": evaluation["actual_winner"],
            "timestamp": evaluation["timestamp"]
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Error in evaluate_response: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/parse-email', methods=['POST'])
def parse_email():
    try:
        data = request.json
        email_content = data.get('email_content', '')
        
        if not email_content:
            return jsonify({"error": "Email content is required"}), 400
        
        # Simple email parsing logic - you can enhance this
        lines = email_content.strip().split('\n')
        
        # Try to extract question (look for common patterns)
        question_start = -1
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['question:', 'issue:', 'problem:', 'help:', 'how to', 'how do']):
                question_start = i
                break
        
        if question_start == -1:
            # If no clear question marker, take the main content
            question = email_content
        else:
            # Take everything from question start onwards
            question = '\n'.join(lines[question_start:])
        
        # Clean up the question
        question = question.replace('Question:', '').replace('Issue:', '').replace('Problem:', '').strip()
        
        return jsonify({
            "question": question,
            "context": "Customer email inquiry"
        })
        
    except Exception as e:
        print(f"❌ Error in parse_email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-ai-response', methods=['POST'])
def generate_ai_response():
    try:
        data = request.json
        question = data.get('question', '')
        context = data.get('context', '')
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        # Generate AI response using the tester
        print(f"🤖 Generating AI response for question...")
        ai_response = tester.generate_ai_response(question, context)
        
        if not ai_response:
            return jsonify({"error": "Failed to generate AI response"}), 500
        
        return jsonify({
            "ai_response": ai_response,
            "question": question,
            "context": context
        })
        
    except Exception as e:
        print(f"❌ Error in generate_ai_response: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-ai-response-stream', methods=['POST'])
def generate_ai_response_stream():
    try:
        data = request.json
        question = data.get('question', '')
        context = data.get('context', '')
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        def generate():
            try:
                # Create a temporary thread for this question
                thread = assistant.client.beta.threads.create(
                    tool_resources={
                        "file_search": {
                            "vector_store_ids": [assistant.vector_store_id]
                        }
                    }
                )
                
                # Add the question with context
                full_question = f"{question}\n\nContext: {context}" if context else question
                
                assistant.client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=full_question
                )
                
                # Run the assistant with streaming
                run = assistant.client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=assistant.assistant_id,
                    instructions="""You are an expert in AKS (Azure Kubernetes Service) support. 
                    Provide a comprehensive, technically accurate response to this customer question.
                    Use the documentation to provide specific guidance and actionable steps.
                    Include relevant references and be professional in your tone.
                    Format your response as plain text suitable for email, do not give any markdown formatting at all.""",
                    tools=[{"type": "file_search"}],
                    stream=True
                )
                
                response_content = ""
                
                for event in run:
                    if event.event == 'thread.message.delta':
                        for content in event.data.delta.content:
                            if hasattr(content, 'text') and hasattr(content.text, 'value'):
                                chunk = content.text.value
                                response_content += chunk
                                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                    elif event.event == 'thread.run.completed':
                        # Process final content with citations
                        messages = assistant.client.beta.threads.messages.list(thread_id=thread.id)
                        for message in messages:
                            if message.role == "assistant":
                                for content in message.content:
                                    if hasattr(content, 'text'):
                                        text_content = content.text.value
                                        annotations = getattr(content.text, 'annotations', [])
                                        final_content = assistant.process_citations(text_content, annotations)
                                        
                                        # Send any remaining content
                                        if len(final_content) > len(response_content):
                                            remaining = final_content[len(response_content):]
                                            yield f"data: {json.dumps({'content': remaining, 'done': False})}\n\n"
                                        
                                        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                                        return
                
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
        
        return Response(
            generate(),
            content_type='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        print(f"❌ Error in generate_ai_response_stream: {e}")
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    print("🌟 Starting AKS Grader API Server...")
    
    # Check environment variables
    if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
        print("❌ Please set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables")
        exit(1)
    
    # Initialize components
    if not initialize_components():
        print("❌ Failed to initialize components")
        exit(1)
    
    app.run(debug=True, port=5000)