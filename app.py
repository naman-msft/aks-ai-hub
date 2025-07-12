from flask import Flask, send_from_directory, request, jsonify, Response
from flask_cors import CORS
import os
import sys
import json
import traceback

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

# Import all the API functionality
from ai_grader import AIResponseGrader, AKSResponseTester
from aks import AKSWikiAssistant

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
                # Generate response using the assistant
                response = assistant.generate_response(question, context)
                
                # Stream the response
                for chunk in response:
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                yield "data: {\"status\": \"complete\"}\n\n"
                
            except Exception as e:
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
       
# Add a dashboard endpoint for future assistant selection
@app.route('/api/assistants', methods=['GET'])
def get_assistants():
    """Get list of available assistants"""
    assistants = [
        {
            "id": "aks-support",
            "name": "AKS Support Assistant",
            "description": "Generate responses to Azure Kubernetes Service customer emails",
            "icon": "🚀",
            "status": "active"
        },
        {
            "id": "prd-writer",
            "name": "PRD Writer",
            "description": "Generate Product Requirements Documents",
            "icon": "📝",
            "status": "coming-soon"
        },
        {
            "id": "doc-assistant",
            "name": "Documentation Assistant",
            "description": "Generate technical documentation and guides",
            "icon": "📚",
            "status": "coming-soon"
        },
        {
            "id": "code-reviewer",
            "name": "Code Review Assistant",
            "description": "Automated code review and suggestions",
            "icon": "👨‍💻",
            "status": "coming-soon"
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

if __name__ == '__main__':
    # Initialize components on startup
    initialize_components()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)