from dotenv import load_dotenv
load_dotenv()
from flask import Flask, send_from_directory, request, jsonify, Response
from flask_cors import CORS
import os
import sys
import json
import traceback
# Add this import
from prd_agent import PRDAgent

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

# Import all the API functionality
from ai_grader import AIResponseGrader, AKSResponseTester
from aks import AKSWikiAssistant
# Initialize components
assistant = None
grader = None
tester = None
prd_agent = None

def initialize_components():
    global assistant, grader, tester, prd_agent
    try:
        print("🚀 Initializing AKS Assistant...")
        assistant = AKSWikiAssistant()
        grader = AIResponseGrader()
        tester = AKSResponseTester(assistant, grader)
        prd_agent = PRDAgent()
        
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
    return jsonify({"status": "healthy", "message": "AKSAI Hub API is running"})

@app.route('/api/parse-email', methods=['POST'])
def parse_email():
    try:
        data = request.json
        email_text = data.get('email_text', '')
        
        if not email_text:
            return jsonify({"error": "Email text is required"}), 400
        
        # Simple email parsing logic - you can enhance this
        lines = email_text.strip().split('\n')
        
        # Try to extract question (look for common patterns)
        question_start = -1
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['question:', 'issue:', 'problem:', 'help:', 'how to', 'how do']):
                question_start = i
                break
        
        if question_start == -1:
            # If no clear question marker, take the main content
            question = email_text
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
        print(f"❌ Error parsing email: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-response', methods=['POST'])
def generate_response():
    try:
        data = request.json
        question = data.get('question', '')
        context = data.get('context', '')
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        # Initialize components if not already done
        if not assistant:
            if not initialize_components():
                return jsonify({"error": "Failed to initialize components"}), 500
        
        def generate():
            yield "data: {\"status\": \"starting\"}\n\n"
            
            try:
                # Use the same ask_question method as CLI with streaming
                full_question = f"{question}\n\nContext: {context}" if context else question
                
                # Use streaming version
                response_started = False
                for chunk in assistant.ask_question(full_question, stream=True):
                    if not response_started:
                        yield "data: {\"status\": \"generating\"}\n\n"
                        response_started = True
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                yield "data: {\"status\": \"complete\"}\n\n"
                
            except Exception as e:
                print(f"❌ Streaming error: {e}")
                traceback.print_exc()
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        print(f"❌ Error generating response: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate_response():
    try:
        data = request.json
        question = data.get('question', '')
        human_response = data.get('human_response', '')
        context = data.get('context', '')
        
        if not question or not human_response:
            return jsonify({"error": "Question and human response are required"}), 400
        
        # Initialize components if not already done
        if not assistant:
            if not initialize_components():
                return jsonify({"error": "Failed to initialize components"}), 500
        
        print(f"🧪 Processing evaluation request...")
        
        # Use the tester to evaluate responses
        evaluation_result = tester.test_response_quality(
            question=question,
            human_response=human_response,
            context=context,
            label_responses=True
        )
        
        print(f"🔍 Debug - Evaluation result keys: {list(evaluation_result.keys())}")
        
        if "error" in evaluation_result:
            print(f"❌ Error in evaluation: {evaluation_result['error']}")
            return jsonify({"error": evaluation_result["error"]}), 500
        
        # Debug the structure
        if "responses" in evaluation_result:
            print(f"✅ Found responses in evaluation_result")
            print(f"🔍 Response keys: {list(evaluation_result['responses'].keys())}")
        else:
            print(f"❌ No 'responses' key found in evaluation_result")
            print(f"🔍 Available keys: {list(evaluation_result.keys())}")
        
        if "response_labels" in evaluation_result:
            print(f"✅ Found response_labels: {evaluation_result['response_labels']}")
        else:
            print(f"❌ No 'response_labels' key found")
        
        # Extract the AI response safely
        try:
            ai_response = evaluation_result["responses"]["response_a"] if evaluation_result["response_labels"]["response_a"] == "AI" else evaluation_result["responses"]["response_b"]
            print(f"✅ Successfully extracted AI response")
        except KeyError as e:
            print(f"❌ KeyError extracting AI response: {e}")
            return jsonify({"error": f"Missing key in evaluation result: {e}"}), 500
        
        # Format response exactly as the frontend expects
        response_data = {
            "evaluation_id": evaluation_result["evaluation_id"],
            "question": question,
            "ai_response": ai_response,
            "human_response": human_response,
            "evaluation": evaluation_result["evaluation"],
            "labels": evaluation_result["response_labels"],
            "winner": evaluation_result["actual_winner"],
            "timestamp": evaluation_result["timestamp"]
        }
        
        print(f"✅ Sending response with keys: {list(response_data.keys())}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error evaluating response: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
       
@app.route('/api/assistants', methods=['GET'])
def get_assistants():
    assistants = [
        {
            "id": "aks-support",
            "name": "AKS Support Assistant",
            "description": "Expert help for Azure Kubernetes Service issues",
            "icon": "🚀",
            "status": "active"
        },
        {
            "id": "prd-writer",
            "name": "PRD Writer",
            "description": "Generate professional Product Requirement Documents",
            "icon": "📝",
            "status": "active"
        },
        {
            "id": "prd-builder",
            "name": "PRD Builder (Section by Section)",
            "description": "Build PRDs section by section with review and editing",
            "icon": "🏗️",
            "status": "active"
        }
    ]
    return jsonify(assistants)

# Serve React App
@app.route('/')
def serve_react_app():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')
    
@app.route('/api/prd/sections', methods=['GET'])
def get_prd_sections():
    """Get all PRD sections configuration"""
    try:
        sections = prd_agent.get_prd_sections()
        return jsonify({"sections": sections})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/prd/generate-section', methods=['POST'])
def generate_prd_section():
    """Generate a single PRD section"""
    try:
        data = request.json
        section_id = data.get('section_id')
        context = data.get('context', {})
        previous_sections = data.get('previous_sections', {})
        
        content = prd_agent.generate_prd_section(section_id, context, previous_sections)
        
        return jsonify({
            "section_id": section_id,
            "content": content
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/prd/regenerate-section', methods=['POST'])
def regenerate_prd_section():
    """Regenerate a section with feedback"""
    try:
        data = request.json
        section_id = data.get('section_id')
        context = data.get('context', {})
        previous_sections = data.get('previous_sections', {})
        feedback = data.get('feedback', '')
        
        # Add feedback to context
        context['user_feedback'] = feedback
        
        content = prd_agent.generate_prd_section(section_id, context, previous_sections)
        
        return jsonify({
            "section_id": section_id,
            "content": content
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/prd/create-stream', methods=['POST'])
def create_prd_stream():
    """Create PRD with section-by-section streaming"""
    # Get request data BEFORE the generator function
    global prd_agent
    
    # Initialize components if not already done
    if not prd_agent:
        if not initialize_components():
            return jsonify({'type': 'error', 'error': 'Failed to initialize components'}), 500
    
    # Get data from request OUTSIDE the generator
    data = request.get_json()
    prompt = data.get('prompt', '')
    context = data.get('context', '')
    data_sources = data.get('data_sources', [])
    
    if not prompt:
        return jsonify({'type': 'error', 'error': 'Prompt is required'}), 400
    
    def generate():
        try:
            # Stream sections using the data we captured outside
            for section_data in prd_agent.create_prd_stream(prompt, context, data_sources):
                yield f"data: {json.dumps(section_data)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")

@app.route('/api/prd/create', methods=['POST'])
def create_prd():
    try:
        # Initialize components if not already done
        if not prd_agent:
            if not initialize_components():
                return jsonify({"error": "Failed to initialize components"}), 500
        data = request.json
        prompt = data.get('prompt', '')
        context = data.get('context', '')
        data_sources = data.get('data_sources', [])
        
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
        
        # Check if Azure OpenAI is configured
        if not os.environ.get("AZURE_OPENAI_KEY") or not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            return jsonify({"error": "Azure OpenAI not configured. Please set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT environment variables."}), 500
        
        result = prd_agent.create_prd(prompt, context, data_sources)
        
        if result.get("success"):
            return jsonify({
                "prd": result["prd"],
                "message": "PRD created successfully"
            })
        else:
            return jsonify({"error": result.get("error", "Unknown error occurred")}), 500
            
    except Exception as e:
        print(f"Error creating PRD: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/prd/continue-generation', methods=['POST'])
def continue_prd_generation():
    """Continue PRD generation from a specific section"""
    global prd_agent
    
    if not prd_agent:
        if not initialize_components():
            return jsonify({'type': 'error', 'error': 'Failed to initialize components'}), 500
    
    data = request.get_json()
    prompt = data.get('prompt', '')
    context = data.get('context', '')
    data_sources = data.get('data_sources', [])
    previous_sections = data.get('previous_sections', {})
    start_from_index = data.get('start_from_index', 0)
    
    def generate():
        try:
            # Continue from the specified section
            for section_data in prd_agent.continue_from_section(prompt, context, data_sources, previous_sections, start_from_index):
                yield f"data: {json.dumps(section_data)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")

@app.route('/api/prd/review', methods=['POST'])
def review_prd():
    try:
        # Initialize components if not already done
        if not prd_agent:
            if not initialize_components():
                return jsonify({"error": "Failed to initialize components"}), 500
        data = request.json
        prd_text = data.get('prd_text', '')
        
        if not prd_text:
            return jsonify({"error": "PRD text is required"}), 400
        
        # Check if Azure OpenAI is configured
        if not os.environ.get("AZURE_OPENAI_KEY") or not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            return jsonify({"error": "Azure OpenAI not configured. Please set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT environment variables."}), 500
        
        result = prd_agent.review_prd(prd_text)
        
        if result.get("success"):
            return jsonify({
                "review": result["review"],
                "score": result["score"],
                "message": "PRD reviewed successfully"
            })
        else:
            return jsonify({"error": result.get("error", "Unknown error occurred")}), 500
            
    except Exception as e:
        print(f"Error reviewing PRD: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    
if __name__ == '__main__':
    # Initialize components on startup
    initialize_components()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)