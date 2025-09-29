from dotenv import load_dotenv
load_dotenv()  # Load .env file
import os
import json
from typing import Dict, List, Optional
import docx
from docx import Document
from docx.shared import Inches
from io import BytesIO
from openai import AzureOpenAI
from aks import AKSWikiAssistant
from dotenv import load_dotenv
import tempfile
import base64
import requests
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool
from azure.identity import DefaultAzureCredential
import re
# Load environment variables from .env file
load_dotenv()

class PRDAgent:
    def __init__(self):
        """Initialize PRD Agent with Azure OpenAI client and configuration"""
        print("🐛 DEBUG: Starting PRDAgent initialization...")
        print(f"API Key set: {'Yes' if os.getenv('AZURE_OPENAI_API_KEY') else 'No'}")
        print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
        
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-04-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        # Set up configuration
        self.prd_model = os.getenv("AZURE_OPENAI_MODEL_PRD", "gpt-5")
        self.bing_connection_id = os.getenv("AZURE_BING_CONNECTION_ID")
        
        # Initialize wiki assistant for internal searches
        try:
            self.wiki_assistant = AKSWikiAssistant()
            print("🐛 DEBUG: ✅ Wiki assistant initialized")
        except Exception as e:
            print(f"⚠️  Could not initialize wiki assistant: {e}")
            self.wiki_assistant = None
        
        print("🐛 DEBUG: ✅ PRDAgent initialization complete")

    def review_prd(self, prd_text: str) -> Dict:
        """Review an existing PRD and provide feedback with section-specific comments"""
        try:
            system_prompt = """
            You are an expert PRD reviewer for Azure Kubernetes Service (AKS).
            Review the provided PRD and give detailed feedback with specific comments.
            
            Structure your response as follows:
            1. Overall Summary (2-3 sentences)
            2. Section-by-Section Comments (for each identifiable section, provide specific feedback)
            3. Recommendations for improvement
            
            For section comments, format like:
            **Section: [Section Name]**
            - Comment: [Specific feedback]
            - Suggestion: [Specific improvement]
            
            Provide feedback on:
            - Completeness and detail level
            - Technical accuracy for AKS
            - Clarity and structure
            - Missing information
            - Alignment with AKS best practices
            """
            
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_MODEL_PRD"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review this PRD:\n\n{prd_text}"}
                ]
            )
            
            review_content = response.choices[0].message.content
            
            # Parse the review to extract section-specific comments
            comments = self._parse_review_comments(review_content, prd_text)
            
            return {
                "success": True,
                "review": review_content,
                "comments": comments,
                "score": self._calculate_prd_score(prd_text),
                "message": "PRD reviewed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_review_comments(self, review_content: str, original_text: str) -> List[Dict]:
        """Parse review content to extract section-specific comments"""
        comments = []
        
        # Split review into sections based on **Section:** markers
        import re
        section_pattern = r'\*\*Section:\s*([^*]+)\*\*\s*\n(.*?)(?=\*\*Section:|$)'
        matches = re.findall(section_pattern, review_content, re.DOTALL)
        
        for section_name, comment_text in matches:
            section_name = section_name.strip()
            
            # Extract comment and suggestion from the text
            comment_lines = [line.strip() for line in comment_text.split('\n') if line.strip()]
            comment = ""
            suggestion = ""
            
            for line in comment_lines:
                if line.startswith('- Comment:'):
                    comment = line.replace('- Comment:', '').strip()
                elif line.startswith('- Suggestion:'):
                    suggestion = line.replace('- Suggestion:', '').strip()
            
            if comment or suggestion:
                comments.append({
                    "section": section_name,
                    "comment": comment,
                    "suggestion": suggestion
                })
        
        return comments
    
    def search_wiki(self, query: str) -> str:
        """Search internal wiki using the AKSWikiAssistant - using the working pattern from aks.py"""
        if not self.wiki_assistant:
            return ""
        
        try:
            # Use the same streaming approach that works in aks.py
            result_generator = self.wiki_assistant.ask_question(
                question=f"Find information about: {query}. Be concise and focus on key points.",
                return_response=False,  # Use False to get generator
                stream=True  # Use True for streaming
            )
            
            # Collect the streamed response
            full_response = ""
            if result_generator:
                for chunk in result_generator:
                    if chunk:
                        full_response += str(chunk)
            
            if full_response:
                # Extract any URLs from the response if they exist
                # Look for patterns like [View this page online](URL) or <a href="URL">
                import re
                
                # Try to extract URLs from HTML links
                url_pattern = r'href="([^"]+)"'
                urls = re.findall(url_pattern, full_response)
                
                # Clean up the response - remove HTML for PRD context
                clean_response = re.sub(r'<[^>]+>', '', full_response)
                clean_response = clean_response[:1000] + "..." if len(clean_response) > 1000 else clean_response
                
                return clean_response
            return ""
            
        except Exception as e:
            print(f"Wiki search error: {e}")
            return ""
    
    def search_with_bing(self, query: str) -> tuple[str, list]:
        """Search using Bing grounding via Azure AI Projects - create fresh client each time"""
        print(f"DEBUG: Bing search called for: {query}")
        
        if not self.bing_connection_id:
            print(f"DEBUG: Missing Bing connection")
            return "", []
        
        try:
            # Create a fresh project client for each search
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
            
            project_client = AIProjectClient(
                endpoint=os.environ.get("PROJECT_ENDPOINT"),
                credential=DefaultAzureCredential(),
            )
            
            instructions = """You are an expert Azure Kubernetes Service (AKS) support assistant. 

    When searching for information:
    1. Search the web for current, relevant information about the specific problem
    2. Focus on official Microsoft documentation and Azure GitHub repositories
    3. Include relevant links and citations from your search results"""

            with project_client:
                agents_client = project_client.agents
                print("DEBUG: Got agents client")
                
                # Initialize Bing grounding tool
                bing = BingGroundingTool(connection_id=self.bing_connection_id)
                print("DEBUG: Created BingGroundingTool")
                
                # Create agent with Bing grounding
                agent = agents_client.create_agent(
                    model=os.environ.get("AZURE_OPENAI_MODEL_PRD"),
                    name="prd-search-assistant",
                    instructions=instructions,
                    tools=bing.definitions,
                )
                print(f"DEBUG: Created agent: {agent.id}")
                
                # Create thread
                thread = agents_client.threads.create()
                print(f"DEBUG: Created thread: {thread.id}")
                
                # Create search query
                search_query = f"""Search for information about: {query}

    **SEARCH PRIORITY INSTRUCTIONS:**
    1. FIRST search these official sources (prioritize these heavily):
    - site:github.com/Azure/AKS for official GitHub repository
    - site:learn.microsoft.com/en-us/azure/aks/ for official Microsoft Learn documentation

    2. If needed, search other relevant sources

    Use search operators like:
    - site:learn.microsoft.com/en-us/azure/aks/ {query}
    - site:github.com/Azure/AKS {query}"""
                
                # Create message with proper format
                message = agents_client.messages.create(
                    thread_id=thread.id,
                    role=MessageRole.USER,
                    content=[{"type": "text", "text": search_query}],
                )
                print(f"DEBUG: Created message")
                
                # Run and process
                run = agents_client.runs.create_and_process(
                    thread_id=thread.id, 
                    agent_id=agent.id
                )
                print(f"DEBUG: Run finished with status: {run.status}")
                
                # Check if run was successful
                if run.status == "failed":
                    print(f"DEBUG: Run failed: {run.last_error}")
                    agents_client.delete_agent(agent.id)
                    return "", []
                
                # Check run steps to see if Bing was used
                run_steps = agents_client.run_steps.list(thread_id=thread.id, run_id=run.id)
                
                step_count = 0
                used_bing = False
                for step in run_steps:
                    step_count += 1
                    print(f"Step {step.get('id')} status: {step.get('status')}")
                    step_details = step.get("step_details", {})
                    tool_calls = step_details.get("tool_calls", [])
                    
                    if tool_calls:
                        print("  Tool calls:")
                        for call in tool_calls:
                            print(f"    Tool Call ID: {call.get('id')}")
                            print(f"    Type: {call.get('type')}")
                            
                            if call.get('type') == 'bing_grounding':
                                used_bing = True
                                bing_details = call.get("bing_grounding", {})
                                if bing_details:
                                    print(f"    Bing Grounding ID: {bing_details.get('requesturl')}")
                    print()
                
                print(f"Found {step_count} run steps total")
                
                # Get the agent's response
                response_message = agents_client.messages.get_last_message_by_role(
                    thread_id=thread.id, 
                    role=MessageRole.AGENT
                )
                
                response_text = ""
                citations = []
                
                if response_message:
                    # Extract text
                    for text_message in response_message.text_messages:
                        response_text += text_message.text.value
                    
                    # Extract URL citations
                    for annotation in response_message.url_citation_annotations:
                        citations.append({
                            'title': annotation.url_citation.title,
                            'url': annotation.url_citation.url
                        })
                        print(f"Found citation: {annotation.url_citation.title}")
                
                # Clean up
                agents_client.delete_agent(agent.id)
                print("Deleted agent")
                
                return response_text, citations
                
        except Exception as e:
            print(f"Bing search error: {e}")
            import traceback
            traceback.print_exc()
            return "", []

    def _load_prd_template(self) -> Dict:
        """Load PRD template structure"""
        return {
            "title": "",
            "sections": [
                {
                    "title": "Executive Summary",
                    "content": "",
                    "description": "Brief overview of the feature/product"
                },
                {
                    "title": "Problem Statement",
                    "content": "",
                    "description": "What problem are we solving?"
                },
                {
                    "title": "Goals and Objectives",
                    "content": "",
                    "description": "What are we trying to achieve?"
                },
                {
                    "title": "Target Audience",
                    "content": "",
                    "description": "Who is this for?"
                },
                {
                    "title": "Requirements",
                    "content": "",
                    "description": "Functional and non-functional requirements"
                },
                {
                    "title": "Technical Considerations",
                    "content": "",
                    "description": "Technical constraints and considerations"
                },
                {
                    "title": "Success Metrics",
                    "content": "",
                    "description": "How will we measure success?"
                },
                {
                    "title": "Timeline",
                    "content": "",
                    "description": "Key milestones and deadlines"
                }
            ]
        }
    
    def create_prd(self, prompt: str, context: str = "", data_sources: List[Dict] = None) -> Dict:
        """Create a new PRD based on user prompt and optional data sources"""
        try:
            # Prepare context from data sources
            additional_context = ""
            if data_sources:
                additional_context = "\n\nAdditional Context from Data Sources:\n"
                for source in data_sources:
                    additional_context += f"\n--- {source['name']} ({source['type']}) ---\n"
                    additional_context += source['content'][:1000]  # Limit content length
                    additional_context += "\n"
            
            system_prompt = f"""
            You are a Product Requirements Document (PRD) writer for Azure Kubernetes Service (AKS).
            Create a comprehensive PRD based on the user's request.
            
            Structure the PRD with these sections:
            1. Executive Summary
            2. Problem Statement  
            3. Goals and Objectives
            4. Target Audience
            5. Requirements (Functional & Non-Functional)
            6. Technical Considerations
            7. Success Metrics
            8. Timeline
            
            Make it specific to AKS and include relevant technical details.
            Use the additional context provided to create a more accurate and detailed PRD.
            
            {additional_context}
            """
            
            user_prompt = f"Create a PRD for: {prompt}"
            if context:
                user_prompt += f"\nContext: {context}"
            
            response = self.client.chat.completions.create(
                model=os.environ.get("AZURE_OPENAI_MODEL_PRD"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            prd_content = response.choices[0].message.content
            
            return {
                "success": True,
                "prd": prd_content,
                "message": "PRD created successfully"
            }
            
        except Exception as e:
            print(f"Error in create_prd: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def review_prd_stream(self, prd_text: str):
        """Stream PRD review with real-time feedback generation"""
        try:
            system_prompt = """You are an expert PRD reviewer for Azure Kubernetes Service (AKS).
            
    Review the provided PRD and provide detailed feedback. Structure your response as:

    1. **Overall Summary** - Brief assessment
    2. **Section-by-Section Comments** - For each section found, provide:
    - **Section: [Name]** (Line X-Y)
    - Comment: [Specific feedback]
    - Suggestion: [Improvement recommendation]
    3. **Final Recommendations**

    Focus on: completeness, technical accuracy, clarity, AKS best practices."""

            response = self.client.chat.completions.create(
                model=self.prd_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review this PRD:\n\n{prd_text}"}
                ],
                stream=True
            )
            
            content = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    content += delta
                    yield {"content": delta, "status": "streaming"}
            
            yield {"status": "complete", "full_content": content}
            
        except Exception as e:
            yield {"error": str(e), "status": "error"}
            
    def generate_prd_section(self, section_id: str, context: Dict, previous_sections: Dict = None) -> str:
        """Generate a single PRD section"""
        # Load sections configuration
        with open('prd_sections.json', 'r') as f:
            sections_config = json.load(f)
        
        # Find the section config
        section = next((s for s in sections_config['sections'] if s['id'] == section_id), None)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        
        # Build the prompt
        prompt = section['prompt']
        
        # Add previous sections context if available
        if previous_sections:
            prev_context = "\n\n".join([f"{k}: {v}" for k, v in previous_sections.items()])
            prompt = prompt.replace("{previous_sections}", prev_context)
        else:
            prompt = prompt.replace("{previous_sections}", "")
        
        # Add current context
        context_str = json.dumps(context)
        prompt = prompt.replace("{context}", context_str)
        
        # Generate the section
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[
                {"role": "system", "content": "You are an expert Product Manager writing a PRD."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content

    def get_prd_sections(self) -> List[Dict]:
        """Get all PRD sections configuration"""
        with open('prd_sections.json', 'r') as f:
            sections_config = json.load(f)
        return sections_config['sections']
    
    def create_prd_stream(self, prompt: str, context: str = "", data_sources: List[Dict] = None):
        """Create a PRD section by section with streaming"""
        try:
            # Load sections configuration
            with open('prd_sections.json', 'r') as f:
                sections_config = json.load(f)
            
            sections = sections_config['sections']
            previous_sections = {}
            
            # Process data sources for additional context
            additional_context = ""
            if data_sources:
                for source in data_sources:
                    additional_context += f"\n\nData from {source.get('name', 'Source')}:\n{source.get('content', '')[:1000]}"
            
            # Generate each section
            for section in sorted(sections, key=lambda x: x['order']):
                # Search for relevant information for this section
                search_query = f"{section['title']} {prompt}"
                
                # Search wiki
                wiki_content = self.search_wiki(search_query)

                    
                # Search web with Bing
                web_content, citations = self.search_with_bing(search_query)
                
                # Build the prompt for this section
                section_prompt = section['prompt']
                
                # Add previous sections context
                if previous_sections:
                    prev_context = "\n\n=== PREVIOUS SECTIONS ===\n"
                    for prev_title, prev_content in previous_sections.items():
                        prev_context += f"\n### {prev_title}\n{prev_content}\n"
                    section_prompt = section_prompt.replace("{previous_sections}", prev_context)
                else:
                    section_prompt = section_prompt.replace("{previous_sections}", "")
                
                citations_text = ""
                if citations:
                    citations_text = "\n".join([f"- [{c['title']}]({c['url']})" for c in citations[:5]])
            
                # Enhanced context with web and wiki search
                enhanced_context = f"""Product: {prompt}
                Context: {context}
                {additional_context}

                === Wiki Knowledge ===
                {wiki_content if wiki_content else "No relevant wiki entries found."}

                === Web Research ===
                {web_content[:1000] if web_content else "No relevant web results found."}

                === Available Citations ===
                {citations_text if citations_text else "No citations available."}

                IMPORTANT: When citing sources in your response:
                - For wiki content, use: [[Wiki: AKS Documentation]](https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki)
                - For web sources with known URLs, use the markdown link format: [Source: title](url)
                - Include the actual URL from the citations list above when available
                - Never use 'internal' or 'localhost' as URLs - use real documentation links"""
                section_prompt = section_prompt.replace("{context}", enhanced_context)
                
                # Generate the section with citations
                response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": """You are an expert Product Manager writing a PRD for Azure Kubernetes Service (AKS) features. 
                        Follow the template guidance exactly. 
                        
                        CITATION RULES:
                        - When citing wiki content, use: [[Wiki: AKS Documentation]](https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki)
                        - When citing web sources, use markdown links with actual URLs: [Source: title](url)
                        - Always use the actual URLs from the citations provided
                        - Never use 'internal' or 'localhost' as URLs
                        - Make citations clickable by using proper markdown link syntax
                        
                        DO NOT include the section title in your response. 
                        Start directly with the content.
                        Format tables using proper markdown table syntax with | separators.
                        Format bullet points using - or * at the start of lines.
                        Use proper markdown formatting for headers (###), bold (**text**), and lists."""},
                        {"role": "user", "content": section_prompt + "\n\nIMPORTANT: Provide ONLY the content without the section title. Make all citations clickable using markdown link syntax [text](url)."}
                    ],
                )
                
                section_content = response.choices[0].message.content
                previous_sections[section['title']] = section_content
                
                # Yield this section
                yield {
                    "type": "section",
                    "section_id": section['title'],
                    "title": section['title'],
                    "content": section_content,
                    "order": section['order']
                }
            
            # Yield completion
            yield {
                "type": "complete",
                "message": "PRD generation completed"
            }
                
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e)
            }
    def continue_from_section(self, prompt: str, context: str, data_sources: List[Dict], previous_sections: Dict, start_index: int):
        """Continue PRD generation from a specific section"""
        try:
            with open('prd_sections.json', 'r') as f:
                sections_config = json.load(f)
            
            sections = sections_config['sections']
            
            # Process data sources for additional context
            additional_context = ""
            if data_sources:
                for source in data_sources:
                    additional_context += f"\n\nData from {source.get('name', 'Source')}:\n{source.get('content', '')[:1000]}"
            
            # Generate remaining sections starting from start_index
            for section in sorted(sections, key=lambda x: x['order'])[start_index:]:
                # ADD WIKI AND BING SEARCH HERE - SAME AS create_prd_stream
                search_query = f"{section['title']} {prompt}"
                
                # Search wiki
                wiki_content = self.search_wiki(search_query)

                # Search web with Bing
                web_content, citations = self.search_with_bing(search_query)
                
                section_prompt = section['prompt']
                
                # Add ALL previous sections as context
                if previous_sections:
                    prev_context = "\n\n=== PREVIOUS SECTIONS ===\n"
                    for prev_title, prev_content in previous_sections.items():
                        prev_context += f"\n### {prev_title}\n{prev_content}\n"
                    section_prompt = section_prompt.replace("{previous_sections}", prev_context)
                else:
                    section_prompt = section_prompt.replace("{previous_sections}", "")
                
                # Build citations text
                citations_text = ""
                if citations:
                    citations_text = "\n".join([f"- [{c['title']}]({c['url']})" for c in citations[:5]])
                
                # Enhanced context with wiki and web search
                enhanced_context = f"""Product: {prompt}
                Context: {context}
                {additional_context}

                === Wiki Knowledge ===
                {wiki_content if wiki_content else "No relevant wiki entries found."}

                === Web Research ===
                {web_content[:1000] if web_content else "No relevant web results found."}

                === Available Citations ===
                {citations_text if citations_text else "No citations available."}

                IMPORTANT: When citing sources in your response:
                - For wiki content, use: [[Wiki: AKS Documentation]](https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki)
                - For web sources with known URLs, use the markdown link format: [Source: title](url) from the citations above
                - Include the actual URL from the citations list when available
                - Never use 'internal' or 'localhost' as URLs - use real documentation links"""
                section_prompt = section_prompt.replace("{context}", enhanced_context)
                
                response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": """You are an expert Product Manager writing a PRD for Azure Kubernetes Service (AKS) features. 
                        Follow the template guidance exactly. 
                        
                        CITATION RULES:
                        - When citing wiki content, use: [[Wiki: AKS Documentation]](https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki)
                        - When citing web sources, use markdown links with actual URLs: [Source: title](url)
                        - Always use the actual URLs from the citations provided
                        - Never use 'internal' or 'localhost' as URLs
                        - Make citations clickable by using proper markdown link syntax
                        
                        DO NOT include the section title in your response. 
                        Start directly with the content.
                        Format tables using proper markdown table syntax with | separators.
                        Format bullet points using - or * at the start of lines.
                        Use proper markdown formatting for headers (###), bold (**text**), and lists."""},
                        {"role": "user", "content": section_prompt + "\n\nIMPORTANT: Provide ONLY the content without the section title. Make all citations clickable using markdown link syntax [text](url)."}
                    ],
                )
                
                section_content = response.choices[0].message.content
                previous_sections[section['title']] = section_content
                
                yield {
                    "type": "section",
                    "section_id": section['title'],
                    "title": section['title'],
                    "content": section_content,
                    "order": section['order']
                }
            
            yield {
                "type": "complete",
                "message": "PRD generation completed"
            }
                
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e)
            }
            
    def review_prd(self, prd_text: str) -> Dict:
        """Review an existing PRD and provide feedback"""
        try:
            system_prompt = f"""
            You are an expert PRD reviewer for Azure Kubernetes Service (AKS).
            Review the provided PRD and give detailed feedback.
            
            Provide feedback on:
            1. Completeness - Are all sections present and detailed?
            2. Technical Accuracy - Are technical details correct?
            3. Clarity - Is it well-written and clear?
            4. AKS Alignment - Does it align with AKS best practices?
            5. Feasibility - Is it technically feasible?
            
            Provide specific suggestions for improvement.
            """
            
            response = self.client.chat.completions.create(
                model=os.environ.get("AZURE_OPENAI_MODEL_PRD"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review this PRD:\n\n{prd_text}"}
                ]
            )
            
            review_content = response.choices[0].message.content
            
            return {
                "success": True,
                "review": review_content,
                "score": self._calculate_prd_score(prd_text),
                "message": "PRD reviewed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_prd_score(self, prd_text: str) -> int:
        """Calculate a quality score for the PRD"""
        score = 0
        
        required_sections = [
            "executive summary", "problem statement", "goals", 
            "requirements", "technical", "metrics", "timeline"
        ]
        
        prd_lower = prd_text.lower()
        
        for section in required_sections:
            if section in prd_lower:
                score += 10
        
        # Length bonus
        if len(prd_text) > 1000:
            score += 10
        if len(prd_text) > 2000:
            score += 10
        
        return min(score, 100)