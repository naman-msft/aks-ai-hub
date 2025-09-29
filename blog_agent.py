from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from openai import AzureOpenAI
from aks import AKSWikiAssistant
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import MessageRole, BingGroundingTool
from azure.identity import DefaultAzureCredential

class BlogAgent:
    def __init__(self, wiki_assistant=None):
        """Initialize Blog Agent with Azure OpenAI client and configuration"""
        print("🐛 DEBUG: Starting BlogAgent initialization...")
        print(f"API Key set: {'Yes' if os.getenv('AZURE_OPENAI_API_KEY') else 'No'}")
        print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
        
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-04-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        # Set up configuration
        self.blog_model = os.getenv("AZURE_OPENAI_MODEL_PRD", "gpt-4.1")
        self.bing_connection_id = os.getenv("AZURE_BING_CONNECTION_ID")
        
        # Use shared wiki assistant or create new one
        if wiki_assistant:
            self.wiki_assistant = wiki_assistant
            print("🐛 DEBUG: ✅ Using shared wiki assistant")
        else:
            try:
                self.wiki_assistant = AKSWikiAssistant()
                print("🐛 DEBUG: ✅ Created new wiki assistant")
            except Exception as e:
                print(f"⚠️ Could not initialize wiki assistant: {e}")
                self.wiki_assistant = None
        
        print("🐛 DEBUG: ✅ BlogAgent initialization complete")

    def get_blog_types(self) -> List[Dict]:
        """Get available blog types and their configurations"""
        return [
            {
                "id": "microsoft-opensource",
                "name": "Microsoft Open Source Blog",
                "description": "Technical posts about Microsoft's open source projects and contributions",
                "guidelines": "Focus on impact, storytelling, and clear CTAs. 3-4 posts per week perform 150% better.",
                "audience": "Developers, open source community, Microsoft ecosystem"
            },
            {
                "id": "aks-engineering",
                "name": "AKS Engineering Blog",
                "description": "Deep technical content for AKS users and operators",
                "guidelines": "Use clear structure with truncate tags, technical accuracy, and practical guidance.",
                "audience": "AKS users, Kubernetes operators, DevOps engineers"
            },
            {
                "id": "kubernetes",
                "name": "Kubernetes Blog",
                "description": "Community-focused content for the Kubernetes project",
                "guidelines": "Must be vendor-neutral, educational, and follow CNCF guidelines.",
                "audience": "Kubernetes community, developers, platform engineers"
            },
            {
                "id": "cncf",
                "name": "CNCF Blog",
                "description": "Cloud native ecosystem content and thought leadership",
                "guidelines": "Vendor-neutral, technical value, community relevance. No promotional content.",
                "audience": "Cloud native practitioners, CNCF community, enterprise architects"
            }
        ]

    def search_wiki(self, query: str) -> str:
        """Search internal wiki for relevant technical information"""
        if not self.wiki_assistant:
            print("⚠️ No wiki assistant available")
            return ""
        
        try:
            print(f"🔍 Searching wiki for blog research: {query[:100]}...")
            
            # Ensure IDs are loaded
            if not hasattr(self.wiki_assistant, 'vector_store_id') or not self.wiki_assistant.vector_store_id:
                if os.path.exists("vector_store_id.json"):
                    with open("vector_store_id.json", 'r') as f:
                        self.wiki_assistant.vector_store_id = json.load(f)["vector_store_id"]
                        
            if not hasattr(self.wiki_assistant, 'assistant_id') or not self.wiki_assistant.assistant_id:
                if os.path.exists("assistant_id.json"):
                    with open("assistant_id.json", 'r') as f:
                        self.wiki_assistant.assistant_id = json.load(f)["assistant_id"]
            
            # Use the wiki assistant with a blog-specific query
            search_query = f"Find technical information and examples for blog writing about: {query[:200]}. Include specific details, best practices, and real-world usage."
            
            result = self.wiki_assistant.ask_question(search_query, return_response=True, stream=False)
            
            if result:
                final_content = ""
                
                # Handle different result types
                if hasattr(result, '__iter__') and not isinstance(result, str):
                    import time
                    start_time = time.time()
                    timeout_seconds = 15
                    
                    try:
                        for chunk in result:
                            if time.time() - start_time > timeout_seconds:
                                break
                                
                            if isinstance(chunk, str):
                                final_content += chunk
                            elif hasattr(chunk, 'content'):
                                final_content += str(chunk.content)
                                
                            if len(final_content) > 1000:
                                break
                                
                    except Exception as e:
                        print(f"⚠️ Error processing wiki result: {e}")
                        return ""
                        
                elif isinstance(result, str):
                    final_content = result
                else:
                    final_content = str(result)
                
                # Clean up the result
                if final_content and len(final_content.strip()) > 20:
                    cleaned_result = re.sub(r'【\d+:\d+†[^】]*】', '', final_content)
                    cleaned_result = re.sub(r'<[^>]+>', '', cleaned_result)
                    cleaned_result = cleaned_result.strip()
                    
                    if len(cleaned_result) > 800:
                        cleaned_result = cleaned_result[:800] + "..."
                    
                    print(f"✅ Wiki search completed for blog research")
                    return cleaned_result
                    
        except Exception as e:
            print(f"⚠️ Wiki search error: {e}")
            
        return ""

    def search_with_bing(self, query: str) -> Tuple[str, List]:
        """Search for external information using Bing"""
        if os.getenv("DISABLE_BING_SEARCH", "false").lower() == "true":
            print("DEBUG: Bing search disabled")
            return "", []
            
        if not self.bing_connection_id:
            print("DEBUG: Missing Bing connection")
            return "", []
            
        try:
            import time
            start_time = time.time()
            timeout_seconds = 20
            
            project_client = AIProjectClient(
                endpoint=os.environ.get("PROJECT_ENDPOINT"),
                credential=DefaultAzureCredential(),
            )
            
            instructions = """You are a technical research assistant for blog writing. 
            Search for current trends, best practices, and real-world examples related to the query.
            Focus on authoritative sources and recent developments."""

            with project_client:
                agents_client = project_client.agents
                
                bing = BingGroundingTool(connection_id=self.bing_connection_id)
                
                agent = agents_client.create_agent(
                    model="gpt-4.1",
                    name="blog-research-assistant",
                    instructions=instructions,
                    tools=bing.definitions,
                )
                
                thread = agents_client.threads.create()
                
                search_query = f"Research latest information for blog writing about: {query[:150]}"
                
                message = agents_client.messages.create(
                    thread_id=thread.id,
                    role=MessageRole.USER,
                    content=[{"type": "text", "text": search_query}],
                )
                
                run = agents_client.runs.create_and_process(
                    thread_id=thread.id,
                    assistant_id=agent.id,
                )
                
                if run.status == 'completed':
                    messages = agents_client.messages.list(
                        thread_id=thread.id,
                        order="desc",
                        limit=10
                    )
                    
                    for message in messages.data:
                        if message.role == "assistant":
                            for content in message.content:
                                if hasattr(content, 'text') and hasattr(content.text, 'value'):
                                    # Extract URLs from citations if available
                                    citations = []
                                    if hasattr(content.text, 'annotations'):
                                        for annotation in content.text.annotations:
                                            if hasattr(annotation, 'url'):
                                                citations.append(annotation.url)
                                    
                                    try:
                                        agents_client.delete_agent(agent.id)
                                    except:
                                        pass
                                        
                                    return content.text.value, citations
                
                try:
                    agents_client.delete_agent(agent.id)
                except:
                    pass
                    
        except Exception as e:
            print(f"⚠️ Bing search error: {e}")
            
        return "", []

    def create_blog_post(self, blog_type: str, raw_content: str, title: str = "", 
                        target_audience: str = "", additional_context: str = "") -> Dict:
        """Create a blog post based on type and raw content"""
        
        blog_configs = {
            "microsoft-opensource": {
                "system_prompt": self._get_microsoft_opensource_prompt(),
                "max_words": 1200,
                "required_sections": ["Purpose/Impact", "Story", "Call-to-Action"]
            },
            "aks-engineering": {
                "system_prompt": self._get_aks_engineering_prompt(),
                "max_words": 2000,
                "required_sections": ["Front Matter", "Introduction", "Technical Content", "Conclusion"]
            },
            "kubernetes": {
                "system_prompt": self._get_kubernetes_prompt(),
                "max_words": 1500,
                "required_sections": ["Vendor-neutral Content", "Technical Value", "Community Focus"]
            },
            "cncf": {
                "system_prompt": self._get_cncf_prompt(),
                "max_words": 1800,
                "required_sections": ["Technical/Educational Value", "Community Relevance", "Vendor Neutrality"]
            }
        }
        
        if blog_type not in blog_configs:
            return {"success": False, "error": f"Unknown blog type: {blog_type}"}
        
        config = blog_configs[blog_type]
        
        try:
            # Research additional context if needed
            research_context = ""
            if len(raw_content.strip()) < 200:  # If content is brief, do research
                print("🔍 Gathering additional research...")
                
                # Search wiki for internal knowledge
                wiki_results = self.search_wiki(f"{title} {raw_content}")
                if wiki_results:
                    research_context += f"\n\nInternal Knowledge Base:\n{wiki_results}\n"
                
                # Search Bing for current trends
                bing_results, citations = self.search_with_bing(f"{title} {raw_content}")
                if bing_results:
                    research_context += f"\n\nCurrent Industry Information:\n{bing_results}\n"
                    if citations:
                        research_context += f"\nSources: {', '.join(citations[:3])}\n"
            
            # Generate the blog post
            user_prompt = f"""
            Create a {blog_type.replace('-', ' ').title()} blog post based on this information:
            
            **Title**: {title or 'Generate an appropriate title'}
            **Target Audience**: {target_audience or 'Default audience for this blog type'}
            **Raw Content**: {raw_content}
            **Additional Context**: {additional_context}
            
            {research_context}
            
            **Requirements**:
            - Maximum {config['max_words']} words
            - Include all required sections: {', '.join(config['required_sections'])}
            - Follow the style guide precisely
            - Make it engaging and actionable
            - Include proper formatting and structure
            """
            
            response = self.client.chat.completions.create(
                model=self.blog_model,
                messages=[
                    {"role": "system", "content": config["system_prompt"]},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            blog_content = response.choices[0].message.content
            
            # Extract metadata
            metadata = self._extract_blog_metadata(blog_content, blog_type)
            
            return {
                "success": True,
                "blog_content": blog_content,
                "blog_type": blog_type,
                "metadata": metadata,
                "word_count": len(blog_content.split()),
                "research_used": bool(research_context),
                "message": f"Blog post created successfully for {blog_type.replace('-', ' ').title()}"
            }
            
        except Exception as e:
            print(f"❌ Error creating blog post: {e}")
            return {"success": False, "error": str(e)}

    def review_blog_post(self, blog_content: str, blog_type: str) -> Dict:
        """Review and provide feedback on a blog post"""
        
        review_prompts = {
            "microsoft-opensource": """
            Review this Microsoft Open Source blog post for:
            1. IMPACT: Does it ladder up to business goals and highlight why the audience should care?
            2. STORYTELLING: Does it tell a cohesive story rather than just listing updates?
            3. CALL-TO-ACTION: Is there one clear CTA driving readers to Microsoft properties?
            4. AUDIENCE FIT: Is it tailored for the broader channel audience?
            5. PUBLISHING STRATEGY: Consider if this should be consolidated with other content.
            """,
            "aks-engineering": """
            Review this AKS Engineering blog post for:
            1. TECHNICAL ACCURACY: Are all technical details correct and up-to-date?
            2. STRUCTURE: Proper front matter, truncate placement, clear headings?
            3. PRACTICAL VALUE: Does it provide actionable guidance?
            4. CODE EXAMPLES: Are code blocks properly formatted with language identifiers?
            5. IMAGES/MEDIA: Are references to images/diagrams appropriate?
            6. ADMONITIONS: Are callouts used effectively and sparingly?
            """,
            "kubernetes": """
            Review this Kubernetes blog post for:
            1. VENDOR NEUTRALITY: No promotional content or vendor bias?
            2. COMMUNITY VALUE: Educational and beneficial to the Kubernetes community?
            3. TECHNICAL DEPTH: Appropriate level of technical detail?
            4. CONTRIBUTION LINKS: Links to relevant GitHub issues/PRs where applicable?
            5. LICENSING: Follows Creative Commons Attribution requirements?
            6. ORIGINALITY: Content is original or has explicit republication permission?
            """,
            "cncf": """
            Review this CNCF blog post for:
            1. VENDOR NEUTRALITY: Completely vendor-neutral with no promotional content?
            2. TECHNICAL/EDUCATIONAL VALUE: Strong how-to, tutorial, or technical insight?
            3. COMMUNITY RELEVANCE: Addresses real-world challenges and solutions?
            4. CNCF PROJECT FOCUS: Properly focuses on CNCF projects if applicable?
            5. COMPARATIVE NEUTRALITY: Avoids criticism or negative portrayal of any projects?
            6. UPSTREAM CONTRIBUTIONS: Links back to relevant GitHub contributions?
            """
        }
        
        if blog_type not in review_prompts:
            return {"success": False, "error": f"Unknown blog type for review: {blog_type}"}
        
        try:
            system_prompt = f"""
            You are an expert blog editor for {blog_type.replace('-', ' ').title()} publications.
            Provide detailed, constructive feedback focusing on the specific guidelines for this publication.
            
            Structure your review as:
            1. **Overall Assessment** (Strong/Good/Needs Work)
            2. **Strengths** (what works well)
            3. **Areas for Improvement** (specific issues)
            4. **Specific Suggestions** (actionable recommendations)
            5. **Publishing Readiness** (Ready/Minor edits needed/Major revision required)
            
            Be thorough but constructive. Focus on helping the author improve the content.
            """
            
            user_prompt = f"""
            {review_prompts[blog_type]}
            
            **Blog Content to Review:**
            {blog_content}
            
            Please provide comprehensive feedback following the structure outlined in your system prompt.
            """
            
            response = self.client.chat.completions.create(
                model=self.blog_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            review_content = response.choices[0].message.content
            
            # Parse review into structured format
            review_data = self._parse_review_feedback(review_content)
            
            return {
                "success": True,
                "review": review_content,
                "structured_feedback": review_data,
                "blog_type": blog_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error reviewing blog post: {e}")
            return {"success": False, "error": str(e)}

    def _get_microsoft_opensource_prompt(self) -> str:
        return """
        You are an expert content strategist for the Microsoft Open Source blog. Your goal is to create impactful, story-driven content that drives business results.

        **Microsoft Open Source Blog Guidelines:**
        
        **1. HAVE PURPOSE AND DRIVE IMPACT**
        - Every post must ladder up to a business initiative or marketing goal
        - Focus on why customers should care, not just what happened
        - Consider consolidating multiple updates into one impactful story
        - Remember: 3-4 posts per week perform 150% better than daily posting
        
        **2. HAVE A STORY TO TELL**
        - 80% of content that just lists updates performs 35% under benchmark
        - Tell cohesive stories that engage readers emotionally and intellectually
        - Avoid topics too niche for broader audience (they perform 65% under benchmark)
        - Focus on broader appeal while maintaining technical depth
        
        **3. HAVE EFFECTIVE CALL-TO-ACTIONS**
        - Include ONE clear CTA that drives readers to Microsoft properties
        - Guide readers to the next stage of their customer journey
        - Acceptable CTAs: contact info, company/project websites, hiring announcements
        
        **CONTENT STRUCTURE:**
        1. **Compelling Headline** - Clear value proposition
        2. **Hook** - Why should readers care? What's the impact?
        3. **Story** - The journey, challenge, solution, outcome
        4. **Technical Details** - How it works, implementation insights
        5. **Customer/Community Impact** - Real-world benefits and use cases
        6. **Call-to-Action** - One clear next step
        
        **STYLE GUIDELINES:**
        - Write for developers, IT professionals, and open source enthusiasts
        - Balance technical accuracy with accessibility
        - Use concrete examples and real-world scenarios
        - Keep paragraphs concise and scannable
        - Include code snippets where relevant
        - Maintain professional but engaging tone
        
        **WORD COUNT:** Target 800-1200 words for optimal engagement.
        
        Create content that makes readers think "This is why Microsoft's open source work matters to me."
        """

    def _get_aks_engineering_prompt(self) -> str:
        return """
        You are a senior technical writer for the AKS Engineering blog, creating content for Kubernetes operators and DevOps professionals.

        **AKS Engineering Blog Guidelines:**
        
        **CONTENT STRUCTURE:**
        1. **Front Matter** (YAML header with metadata)
        2. **Introduction** (1-3 paragraphs with clear value proposition)
        3. **<!-- truncate -->** (excerpt break for blog listings)
        4. **Technical Content** (main body with practical guidance)
        5. **Conclusion** (summary and next steps)
        
        **FRONT MATTER TEMPLATE:**
        ```yaml
        ---
        title: "Clear, Human-Readable Title (Title Case)"
        date: "YYYY-MM-DD"
        description: "1-2 sentence summary for previews & SEO"
        authors: ["author-name"]
        tags:
          - relevant-tag
          - another-tag
        image: ./hero-image.png
        keywords: ["AKS", "Kubernetes", "Azure"]
        ---
        ```
        
        **WRITING CONVENTIONS:**
        - Use sentence case for section headings (except title)
        - Prefer ## and ### heading levels
        - Use fenced code blocks with language identifiers
        - Wrap inline code/commands in backticks
        - Include meaningful alt text for images
        - Reference images relatively: `![Description](./image-name.webp)`
        
        **ADMONITIONS (use sparingly):**
        - `:::tip Pro Tip` for performance/efficiency hints
        - `:::caution` for side effects/billing/security concerns  
        - `:::danger` for destructive operations
        - `:::note` for important context
        
        **TAG STRATEGY:**
        - Use 2-6 tags per post
        - Combine broad (networking) and specific (azure-front-door) tags
        - Reuse existing tags before creating new ones
        
        **TECHNICAL EXCELLENCE:**
        - All code examples must be tested and working
        - Include proper error handling in examples
        - Reference official documentation where applicable
        - Use correct product names (Azure Kubernetes Service (AKS))
        - Provide step-by-step instructions for complex procedures
        
        **AUDIENCE:** AKS users, Kubernetes operators, DevOps engineers, platform engineers
        
        **WORD COUNT:** 1000-2000 words optimal for technical deep-dives.
        
        Create content that makes readers more effective AKS operators.
        """

    def _get_kubernetes_prompt(self) -> str:
        return """
        You are a technical content creator for the official Kubernetes blog, writing for the global Kubernetes community.

        **Kubernetes Blog Guidelines:**
        
        **CORE PRINCIPLES:**
        - **Vendor Neutrality**: Absolutely no promotional content or vendor bias
        - **Community Value**: Educational content that benefits all Kubernetes users
        - **Technical Excellence**: Accurate, tested, and actionable information
        - **Open Source Spirit**: Collaborative, inclusive, and welcoming tone
        
        **CONTENT CATEGORIES:**
        - Technical tutorials and how-to guides
        - Project updates and feature announcements
        - Community spotlights and case studies
        - Best practices and lessons learned
        - Event recaps and insights
        
        **CONTENT STRUCTURE:**
        1. **Clear Introduction** - Problem statement and value proposition
        2. **Technical Content** - Step-by-step guidance with examples
        3. **Real-world Context** - Why this matters to the community
        4. **Next Steps** - How readers can apply this knowledge
        5. **Contributing Back** - Links to relevant GitHub issues/PRs
        
        **TECHNICAL REQUIREMENTS:**
        - All code examples must be tested on recent Kubernetes versions
        - Include version compatibility information
        - Use standard Kubernetes resource formats (YAML)
        - Reference official Kubernetes documentation
        - Link to relevant KEPs (Kubernetes Enhancement Proposals) when applicable
        
        **STYLE GUIDELINES:**
        - Write for developers, operators, and platform engineers
        - Assume familiarity with Kubernetes basics
        - Use clear, concise language
        - Include practical examples and use cases
        - Maintain encouraging, collaborative tone
        - Credit contributors and community members
        
        **LINKING STRATEGY:**
        - Link to upstream contributions (GitHub issues, PRs)
        - Reference official Kubernetes docs
        - Credit community contributors
        - Avoid vendor-specific documentation unless universally applicable
        
        **COMPLIANCE:**
        - Follow Creative Commons Attribution license
        - Ensure content is original or has explicit republication permission
        - No promotional content for specific vendors
        - Focus on open source solutions
        
        **WORD COUNT:** 800-1500 words for optimal community engagement.
        
        Create content that strengthens and educates the Kubernetes community.
        """

    def _get_cncf_prompt(self) -> str:
        return """
        You are a technical content strategist for the CNCF blog, creating vendor-neutral content for the cloud native community.

        **CNCF Blog Guidelines:**
        
        **CORE VALUES:**
        - **Vendor Neutrality**: Zero promotional content, completely objective
        - **Technical/Educational Value**: Strong how-to, tutorials, and insights
        - **Community Relevance**: Address real-world challenges and solutions  
        - **Collaborative Spirit**: Constructive, positive impact on community
        
        **CONTENT CATEGORIES:**
        - **Technical Guides**: How-to articles and tutorials on CNCF projects
        - **Case Studies**: Real-world CNCF project deployments and outcomes
        - **Thought Leadership**: Cloud native trends and industry developments
        - **Project Updates**: Insights on CNCF Graduated/Incubating projects
        - **Event Content**: Recaps and experiences from CNCF events
        
        **AUTHOR CATEGORIES & GUIDELINES:**
        - **Members**: Vendor-neutral posts aligned with CNCF values
        - **Project Maintainers**: Content focused on CNCF Graduated/Incubating projects
        - **TAG Members**: Posts authored by or on behalf of Technical Advisory Groups
        - **Ambassadors**: Up to 2 posts/month on expertise and thought leadership
        - **Mentorship/Scholarship**: Experience sharing and program impact
        
        **TECHNICAL EXCELLENCE:**
        - Focus on CNCF Graduated and Incubating projects
        - Include links to relevant GitHub contributions
        - Provide working code examples and configurations
        - Reference official project documentation
        - Ensure compatibility information is current
        
        **COMPARATIVE CONTENT RULES:**
        - Help readers navigate technology choices
        - Address legacy issues and platform compatibility
        - **NEVER criticize or negatively portray any projects**
        - Maintain neutral, collaborative tone in comparisons
        - Focus on use case fit rather than "better/worse" judgments
        
        **CONTENT STRUCTURE:**
        1. **Problem Context** - Why this matters to cloud native practitioners
        2. **Technical Solution** - Detailed implementation guidance
        3. **Real-world Application** - Practical use cases and examples
        4. **Community Impact** - How this benefits the ecosystem
        5. **Contributing Back** - Links to upstream contributions
        
        **PROHIBITED CONTENT:**
        - Paid or sponsored posts
        - Press releases or announcements
        - Promotional content for vendors
        - Criticism of projects or technologies
        - Marketing fluff or sales pitches
        
        **AUDIENCE:** Developers, IT operators, cloud native enthusiasts, enterprise architects
        
        **WORD COUNT:** 1000-1800 words for comprehensive technical content.
        
        **REVIEW PROCESS:** All content reviewed by CNCF team within 7-10 business days.
        
        Create content that advances cloud native adoption and community knowledge.
        """

    def _extract_blog_metadata(self, content: str, blog_type: str) -> Dict:
        """Extract metadata from blog content"""
        metadata = {
            "estimated_read_time": max(1, len(content.split()) // 200),  # 200 WPM average
            "word_count": len(content.split()),
            "has_code_blocks": "```" in content,
            "has_images": "![" in content or "<img" in content,
            "has_links": "[" in content and "](" in content,
        }
        
        # Extract front matter if present (for AKS Engineering blogs)
        if blog_type == "aks-engineering" and content.startswith("---"):
            try:
                end_idx = content.find("---", 3)
                if end_idx > 0:
                    front_matter = content[3:end_idx].strip()
                    metadata["has_front_matter"] = True
                    metadata["front_matter"] = front_matter
            except:
                pass
        
        return metadata

    def _parse_review_feedback(self, review_content: str) -> Dict:
        """Parse review content into structured feedback"""
        sections = {
            "overall_assessment": "",
            "strengths": [],
            "improvements": [],
            "suggestions": [],
            "publishing_readiness": ""
        }
        
        try:
            # Simple parsing - look for numbered sections and bullet points
            lines = review_content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Detect section headers
                if "overall assessment" in line.lower():
                    current_section = "overall_assessment"
                elif "strengths" in line.lower():
                    current_section = "strengths"
                elif "areas for improvement" in line.lower() or "improvement" in line.lower():
                    current_section = "improvements"
                elif "suggestions" in line.lower() or "recommendations" in line.lower():
                    current_section = "suggestions"
                elif "publishing readiness" in line.lower() or "readiness" in line.lower():
                    current_section = "publishing_readiness"
                elif line.startswith(('-', '*', '•')) and current_section in ["strengths", "improvements", "suggestions"]:
                    # Bullet point
                    sections[current_section].append(line[1:].strip())
                elif current_section and not line.startswith('#'):
                    # Regular content
                    if current_section in ["overall_assessment", "publishing_readiness"]:
                        sections[current_section] += line + " "
                    
        except Exception as e:
            print(f"⚠️ Error parsing review feedback: {e}")
            
        return sections
