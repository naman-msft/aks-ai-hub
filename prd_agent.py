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
                ],
                temperature=0.7,
                max_tokens=3000
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
                ],
                temperature=0.3,
                max_tokens=1500
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