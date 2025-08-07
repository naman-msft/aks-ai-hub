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
# Load environment variables from .env file
load_dotenv()
class PRDAgent:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_KEY"),
            api_version="2024-02-01",
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
        )
        self.wiki_assistant = AKSWikiAssistant()
        self.prd_template = self._load_prd_template()
        self.deployment_name = os.getenv("AZURE_OPENAI_MODEL_PRD", "gpt-4o")
    
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
                model=os.environ.get("AZURE_OPENAI_MODEL_PRD", "gpt-4.1"),
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
                # Build the prompt for this section
                section_prompt = section['prompt']
                
                # Add ALL previous sections as context (incremental buildup)
                if previous_sections:
                    prev_context = "\n\n=== PREVIOUS SECTIONS ===\n"
                    for prev_title, prev_content in previous_sections.items():
                        prev_context += f"\n### {prev_title}\n{prev_content}\n"
                    section_prompt = section_prompt.replace("{previous_sections}", prev_context)
                else:
                    section_prompt = section_prompt.replace("{previous_sections}", "")
                
                # Add current context
                context_str = f"Product: {prompt}\nContext: {context}\n{additional_context}"
                section_prompt = section_prompt.replace("{context}", context_str)
                
                # Generate the section
                response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": """You are an expert Product Manager writing a PRD for Azure Kubernetes Service (AKS) features. 
                        Follow the template guidance exactly. 
                        DO NOT include the section title in your response. 
                        DO NOT add any preamble like 'Here is', 'Below is', 'Absolutely', etc. 
                        Start directly with the content.
                        Format tables using proper markdown table syntax with | separators.
                        Format bullet points using - or * at the start of lines.
                        Use proper markdown formatting for headers (###), bold (**text**), and lists."""},
                        {"role": "user", "content": section_prompt + "\n\nIMPORTANT: Provide ONLY the content without the section title or any introductory phrases. Use proper markdown formatting."}
                    ],
                )
                
                section_content = response.choices[0].message.content
                # Store with the actual title for context
                previous_sections[section['title']] = section_content
                
                # Yield this section (use title as section_id for simplicity)
                yield {
                    "type": "section",
                    "section_id": section['title'],  # Use title as ID
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
                section_prompt = section['prompt']
                
                # Add ALL previous sections as context
                if previous_sections:
                    prev_context = "\n\n=== PREVIOUS SECTIONS ===\n"
                    for prev_title, prev_content in previous_sections.items():
                        prev_context += f"\n### {prev_title}\n{prev_content}\n"
                    section_prompt = section_prompt.replace("{previous_sections}", prev_context)
                else:
                    section_prompt = section_prompt.replace("{previous_sections}", "")
                
                context_str = f"Product: {prompt}\nContext: {context}\n{additional_context}"
                section_prompt = section_prompt.replace("{context}", context_str)
                
                response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": """You are an expert Product Manager writing a PRD for Azure Kubernetes Service (AKS) features. 
                        Follow the template guidance exactly. 
                        DO NOT include the section title in your response. 
                        DO NOT add any preamble like 'Here is', 'Below is', 'Absolutely', etc. 
                        Start directly with the content.
                        Format tables using proper markdown table syntax with | separators.
                        Format bullet points using - or * at the start of lines.
                        Use proper markdown formatting for headers (###), bold (**text**), and lists."""},
                        {"role": "user", "content": section_prompt + "\n\nIMPORTANT: Provide ONLY the content without the section title or any introductory phrases. Use proper markdown formatting."}
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
                model=os.environ.get("AZURE_OPENAI_MODEL_PRD", "gpt-4.1"),
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