from dotenv import load_dotenv
load_dotenv()
from html import parser
import os
import sys
import json
import argparse
import urllib.parse
import re
from openai import AzureOpenAI
from typing import List, Dict, Optional
import time
import base64
import requests
import hashlib
from ai_grader import AIResponseGrader, AKSResponseTester
from azure.ai.agents.models import BingGroundingTool
from openai import OpenAIError  # if not already imported

TARGET_ASSISTANT_MODEL = os.getenv("AZURE_OPENAI_MODEL_EMAIL", "gpt-5")
STRICT_MODEL = os.getenv("REQUIRE_ASSISTANT_MODEL_STRICT", "false").lower() == "true"
# Configuration
VECTOR_STORE_FILE = "vector_store_id.json"
ASSISTANT_ID_FILE = "assistant_id.json"
SUPPORTED_FORMATS = {".md", ".txt", ".json", ".yaml", ".yml"}
WIKI_URL_MAPPING_FILE = "wiki_url_mapping.json"

# Initialize Bing grounding tool only if connection name is available
def get_bing_grounding_tool():
    print("🐛 DEBUG: Checking BING_CONNECTION_NAME...")
    # connection_name = os.getenv("BING_CONNECTION_NAME")
    connection_name = os.getenv("AZURE_BING_CONNECTION_ID")
    print(f"🐛 DEBUG: BING_CONNECTION_NAME = {connection_name}")
    
    if connection_name:
        print("🐛 DEBUG: Attempting to initialize BingGroundingTool...")
        try:
            tool = BingGroundingTool(connection_id=connection_name)
            print("🐛 DEBUG: ✅ BingGroundingTool initialized successfully")
            return tool
        except Exception as e:
            print(f"⚠️  Could not initialize Bing grounding tool: {e}")
            print(f"🐛 DEBUG: Exception details: {type(e).__name__}: {str(e)}")
            return None
    else:
        print("🐛 DEBUG: No BING_CONNECTION_NAME found, skipping Bing tool")
        return None

class AKSWikiAssistant:
    def __init__(self):
        print("🐛 DEBUG: Starting AKSWikiAssistant initialization...")
        print(f"API Key set: {'Yes' if os.getenv('AZURE_OPENAI_API_KEY') else 'No'}")
        print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
        """Initialize the AKS Wiki Assistant with Azure OpenAI client"""
        
        print("🐛 DEBUG: Creating Azure OpenAI client...")
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-04-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        print("🐛 DEBUG: ✅ Azure OpenAI client created")
        
        self.deployment_name = os.environ.get("AZURE_OPENAI_MODEL_EMAIL")
        self.vector_store_id = None
        self.assistant_id = None
        self.thread_id = None

        # Preload existing vector store id if present
        if os.path.exists(VECTOR_STORE_FILE):
            try:
                with open(VECTOR_STORE_FILE, "r") as f:
                    data = json.load(f)
                    self.vector_store_id = data.get("vector_store_id")
                    if self.vector_store_id:
                        print(f"🐛 DEBUG: Preloaded vector_store_id={self.vector_store_id}")
            except Exception as e:
                print(f"⚠️ Could not preload vector store id: {e}")

        # NOW call ensure_assistant (after vector_store_id is potentially loaded)
        self.assistant = self.ensure_assistant()
        if self.assistant:
            print(f"🐛 DEBUG: Active assistant id={self.assistant.id} model={getattr(self.assistant,'model',None)}")
        else:
            print("❌ Failed to establish assistant")

        
        print("🐛 DEBUG: Loading wiki URL mapping...")
        self.wiki_url_mapping = self.load_wiki_url_mapping()
        print("🐛 DEBUG: ✅ Wiki URL mapping loaded")
        
        print("🐛 DEBUG: Initializing AI grader...")
        self.ai_grader = AIResponseGrader()
        print("🐛 DEBUG: ✅ AI grader initialized")
        
        print("🐛 DEBUG: Initializing response tester...")
        self.response_tester = AKSResponseTester(self, self.ai_grader)
        print("🐛 DEBUG: ✅ Response tester initialized")
        
        print("🐛 DEBUG: Initializing Bing tool...")
        self.bing_tool = get_bing_grounding_tool()
        print(f"🐛 DEBUG: ✅ Bing tool result: {self.bing_tool is not None}")
        
        print("🐛 DEBUG: ✅ AKSWikiAssistant initialization complete")


    def test_against_human_response(self, 
                                   question: str, 
                                   human_response: str,
                                   context: str = "",
                                   show_labels: bool = False) -> Dict:
        """
        Test AI response quality against a human response
        
        Args:
            question: The original question
            human_response: The human-generated response
            context: Additional context
            show_labels: Whether to reveal which response is AI vs human
            
        Returns:
            Dict containing evaluation results
        """
        return self.response_tester.test_response_quality(
            question=question,
            human_response=human_response,
            context=context,
            label_responses=show_labels
        )
    
    def run_evaluation_suite(self, test_cases_file: str = "test_cases.json") -> None:
        """
        Run evaluation suite from a test cases file
        
        Args:
            test_cases_file: Path to JSON file containing test cases
        """
        print(f"🧪 Running evaluation suite from {test_cases_file}...")
        
        try:
            with open(test_cases_file, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
        except FileNotFoundError:
            print(f"❌ Test cases file not found: {test_cases_file}")
            return
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing test cases file: {e}")
            return
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n📝 Running test case {i}/{len(test_cases)}...")
            
            result = self.test_against_human_response(
                question=test_case["question"],
                human_response=test_case["human_response"],
                context=test_case.get("context", ""),
                show_labels=True
            )
            
            results.append(result)
            
            # Print summary for this test case
            if "evaluation" in result:
                winner = result.get("actual_winner", "Unknown")
                print(f"🏆 Winner: {winner}")
                
                scores = result["evaluation"]["scores"]
                total_ai = scores["response_a"]["total"] if result["response_labels"]["response_a"] == "AI" else scores["response_b"]["total"]
                total_human = scores["response_b"]["total"] if result["response_labels"]["response_b"] == "Human" else scores["response_a"]["total"]
                
                print(f"📊 Scores - AI: {total_ai}/60, Human: {total_human}/60")
        
        # Generate final report
        print(f"\n📋 Generating final evaluation report...")
        
        # Count wins
        ai_wins = sum(1 for r in results if r.get("actual_winner") == "AI")
        human_wins = sum(1 for r in results if r.get("actual_winner") == "Human")
        
        print(f"\n🎯 Final Results:")
        print(f"   AI Wins: {ai_wins}")
        print(f"   Human Wins: {human_wins}")
        print(f"   AI Win Rate: {ai_wins/len(results)*100:.1f}%")
        
        # Save results
        results_file = f"evaluation_results_{int(time.time())}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results saved to {results_file}")

    def ensure_assistant(self):
        """
        Ensure we have a retrieval assistant that supports file_search.
        We still use gpt-5 (target generation model) separately for final answer refinement.
        Logic:
          - Try to reuse existing assistant if its model supports file_search.
          - If target (gpt-5) is requested but unsupported with file_search, fall back to RETRIEVAL_ASSISTANT_MODEL (default gpt-4.1).
          - Persist only the retrieval assistant id.
        Sets:
          self.generation_model -> the (possibly unsupported for tools) target model (e.g. gpt-5)
          self.retrieval_model  -> the assistant's model actually used for file_search
        """
        self.generation_model = os.getenv("AZURE_OPENAI_MODEL_EMAIL", "gpt-5")
        fallback_model = os.getenv("RETRIEVAL_ASSISTANT_MODEL", "gpt-4.1")
        target_tool = "file_search"

        existing_id = None
        if os.path.exists(ASSISTANT_ID_FILE):
            try:
                with open(ASSISTANT_ID_FILE, "r") as f:
                    existing_id = json.load(f).get("assistant_id")
            except Exception as e:
                print(f"⚠️ Failed reading {ASSISTANT_ID_FILE}: {e}")

        # Try existing assistant
        if existing_id:
            try:
                asst = self.client.beta.assistants.retrieve(existing_id)
                current_model = getattr(asst, "model", None)
                print(f"🐛 DEBUG: Existing assistant {existing_id} model={current_model}")
                # Keep if model still OK (not None) and we can proceed
                if current_model:
                    self.retrieval_model = current_model
                    # Reattach vector store idempotently
                    if self.vector_store_id:
                        try:
                            self.client.beta.assistants.update(
                                assistant_id=asst.id,
                                tool_resources={"file_search": {"vector_store_ids": [self.vector_store_id]}}
                            )
                        except Exception as e:
                            print(f"⚠️ Could not reattach vector store: {e}")
                    return asst
            except Exception as e:
                print(f"⚠️ Could not retrieve existing assistant {existing_id}: {e}")

        # Decide model for retrieval assistant
        retrieval_model = fallback_model  # force fallback because gpt-5 rejects file_search
        if self.generation_model != fallback_model:
            print(f"ℹ️ '{self.generation_model}' chosen for generation; using '{retrieval_model}' for retrieval (file_search tool support).")

        # Create retrieval assistant
        tools = [{"type": target_tool}]
        try:
            asst = self.client.beta.assistants.create(
                name="AKS Retrieval Assistant",
                instructions=(
                    "You retrieve authoritative Azure Kubernetes Service (AKS) documentation. "
                    "Use file_search to gather source passages. Provide concise, source‑cited summaries."
                ),
                model=retrieval_model,
                tools=tools,
            )
            print(f"✅ Created retrieval assistant {asst.id} on model {retrieval_model}")
        except Exception as e:
            print(f"❌ Failed to create retrieval assistant ({retrieval_model}): {e}")
            return None

        # Attach vector store
        if self.vector_store_id:
            try:
                asst = self.client.beta.assistants.update(
                    assistant_id=asst.id,
                    tool_resources={"file_search": {"vector_store_ids": [self.vector_store_id]}}
                )
                print(f"🔗 Attached vector store {self.vector_store_id}")
            except Exception as e:
                print(f"⚠️ Could not attach vector store {self.vector_store_id}: {e}")

        # Persist
        try:
            with open(ASSISTANT_ID_FILE, "w") as f:
                json.dump({"assistant_id": asst.id}, f)
        except Exception as e:
            print(f"⚠️ Could not write {ASSISTANT_ID_FILE}: {e}")

        self.retrieval_model = retrieval_model
        return asst
    
    def load_wiki_url_mapping(self) -> Dict[str, str]:
        """Load the wiki URL mapping from file"""
        try:
            mapping_path = os.path.join(os.path.dirname(__file__), WIKI_URL_MAPPING_FILE)
            if os.path.exists(mapping_path):
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)
                    print(f"✅ Loaded {len(mapping)} wiki URL mappings")
                    return mapping
            else:
                print(f"⚠️  Wiki URL mapping file not found at {mapping_path}")
                return {}
        except Exception as e:
            print(f"❌ Error loading wiki URL mapping: {e}")
            return {}

    def get_public_url(self, wiki_filename: str) -> Optional[str]:
        """Get the public URL for a wiki file using the mapping"""
        if not self.wiki_url_mapping:
            return None
        
        # Try exact match first
        if wiki_filename in self.wiki_url_mapping:
            mapping_value = self.wiki_url_mapping[wiki_filename]
            # Extract URL from markdown link format
            if mapping_value.startswith('[View this page online](') and mapping_value.endswith(')'):
                return mapping_value[24:-1]  # Remove '[View this page online](' and ')'
        
        # Try without extension
        filename_without_ext = wiki_filename.replace('.md', '')
        for key, value in self.wiki_url_mapping.items():
            if key.replace('.md', '') == filename_without_ext:
                if value.startswith('[View this page online](') and value.endswith(')'):
                    return value[24:-1]
        
        return None
    
    def process_wiki_files(self, wiki_path: str, subpath: str = "AKS", vector_store_id: str = None) -> List[str]:
        """Process cloned wiki files and optionally upload them incrementally"""
        print(f"\n📁 Processing wiki files from: {wiki_path}")
        
        # Look for AKS folder
        aks_path = os.path.join(wiki_path, subpath)
        if not os.path.exists(aks_path):
            print(f"❌ AKS folder not found at {aks_path}")
            return []
        
        processed_files = []
        base_wiki_url = "https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki"
        
        # First, count total files
        total_files = sum(1 for root, dirs, files in os.walk(aks_path) 
                        for file in files if file.endswith('.md'))
        print(f"📊 Found {total_files} markdown files to process")
        
        file_count = 0
        batch_files = []
        batch_size = 50  # Upload every 50 files
        
        for root, dirs, files in os.walk(aks_path):
            for file in files:
                if file.endswith('.md'):
                    file_count += 1
                    file_path = os.path.join(root, file)
                    
                    # Calculate relative path for URL
                    relative_path = os.path.relpath(file_path, wiki_path)
                    wiki_path_for_url = "/" + relative_path.replace('.md', '').replace(os.sep, '/')
                    encoded_path = urllib.parse.quote(wiki_path_for_url)
                    wiki_url = f"{base_wiki_url}?pagePath={encoded_path}"
                    
                    # Read original content
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Add wiki URL at the top if not already present
                        if not content.startswith("[View this page online]"):
                            modified_content = f"[View this page online]({wiki_url})\n\n{content}"
                            
                            # Write back the modified content
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(modified_content)
                        
                        processed_files.append(file_path)
                        
                        # Add to batch for incremental upload
                        if vector_store_id and any(file_path.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                            if os.path.getsize(file_path) > 0:
                                batch_files.append(file_path)
                        
                        # Show progress
                        if file_count % 100 == 0:
                            print(f"  ✓ Processed {file_count}/{total_files} files...")
                        
                        # Upload batch if we hit the batch size
                        if vector_store_id and len(batch_files) >= batch_size:
                            self._upload_batch(vector_store_id, batch_files, file_count - len(batch_files) + 1, file_count)
                            batch_files = []
                        
                    except Exception as e:
                        print(f"  ❌ Error processing {file_path}: {e}")
        
        # Upload any remaining files
        if vector_store_id and batch_files:
            self._upload_batch(vector_store_id, batch_files, file_count - len(batch_files) + 1, file_count)
        
        print(f"✅ Processed {len(processed_files)} wiki files total")
        return processed_files

    def _upload_batch(self, vector_store_id: str, file_paths: List[str], start_idx: int, end_idx: int) -> None:
        """Upload a batch of files to the vector store"""
        print(f"\n  📤 Uploading files {start_idx} to {end_idx}...")
        
        file_streams = []
        for file_path in file_paths:
            try:
                file_streams.append(open(file_path, "rb"))
            except Exception as e:
                print(f"    ❌ Error opening {file_path}: {e}")
        
        if file_streams:
            try:
                file_batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=vector_store_id, 
                    files=file_streams
                )
                print(f"    ✅ Upload complete - Status: {file_batch.status}")
                print(f"    📊 Completed: {file_batch.file_counts.completed}, Failed: {file_batch.file_counts.failed}")
                
                # Show sample of uploaded files
                if file_batch.file_counts.completed > 0:
                    print(f"    📁 Sample files uploaded:")
                    for i, path in enumerate(file_paths[:3]):  # Show first 3
                        print(f"       - {os.path.basename(path)}")
                    if len(file_paths) > 3:
                        print(f"       ... and {len(file_paths) - 3} more")
                        
            except Exception as e:
                print(f"    ❌ Error uploading batch: {e}")
            finally:
                for f in file_streams:
                    f.close()

    def create_or_load_vector_store(self, wiki_path: str, subpath: str = "AKS") -> str:
        """Create or load existing vector store"""
        print(f"\n🗄️  Setting up vector store...")
        
        # Check if vector store already exists
        if os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                self.vector_store_id = data.get('vector_store_id')
                print(f"✅ Loaded existing vector store: {self.vector_store_id}")
                return self.vector_store_id
        
        # Process wiki files first
        processed_files = self.process_wiki_files(wiki_path, subpath, vector_store_id=None)

        if not processed_files:
            print("❌ No wiki files found to process.")
            return None

        # Test connection first
        print("🔌 Testing Azure OpenAI connection...")
        try:
            test_response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": "test"}],
                # max_tokens=10
            )
            print("✅ Connection to Azure OpenAI successful")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print(f"💡 Check your endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
            print(f"💡 It should look like: https://YOUR-RESOURCE-NAME.openai.azure.com/")
            return None

        # Create new vector store only after successful connection
        print("📦 Creating new vector store...")
        try:
            vector_store = self.client.beta.vector_stores.create(name="AKSWikiKnowledge")
            self.vector_store_id = vector_store.id
            
            # Save vector store ID immediately
            with open(VECTOR_STORE_FILE, "w") as f:
                json.dump({"vector_store_id": vector_store.id}, f)
            print(f"💾 Vector store created: {self.vector_store_id}")
            
        except Exception as e:
            print(f"❌ Failed to create vector store: {e}")
            print("💡 Your Azure OpenAI deployment might not support the Assistants API")
            return None

        # Now process and upload files incrementally
        print("\n🚀 Starting incremental file processing and upload...")
        processed_files = self.process_wiki_files(wiki_path, subpath, vector_store.id)

        if not processed_files:
            print("❌ No files were processed successfully")
            return None

        print(f"\n✅ Vector store setup complete: {self.vector_store_id}")
        return self.vector_store_id

    def peek_vector_store(self) -> None:
        """Peek at files in the vector store"""
        if not self.vector_store_id:
            print("❌ No vector store loaded")
            return
        
        print(f"\n👀 Peeking into vector store: {self.vector_store_id}")
        
        # List files in the vector store
        files = self.client.beta.vector_stores.files.list(
            vector_store_id=self.vector_store_id,
            limit=10  # Just show first 10
        )
        
        print(f"\n📄 First few files in vector store:\n")
        for i, file in enumerate(files.data):
            print(f"{i+1}. File ID: {file.id}")
            
            # Retrieve file details
            file_details = self.client.files.retrieve(file.id)
            print(f"   Name: {file_details.filename}")
            print(f"   Size: {file_details.bytes} bytes")
            print(f"   Created: {file_details.created_at}")
            
            # Try to get content preview (if possible)
            try:
                content = self.client.files.content(file.id)
                preview = content.read().decode('utf-8')[:200] + "..."
                print(f"   Preview: {preview}\n")
            except:
                print(f"   Preview: Not available\n")

    def create_or_load_assistant(self) -> str:
        """Create or load existing assistant"""
        print(f"\n🤖 Setting up AI assistant...")
        
        # Check if assistant already exists
        if os.path.exists(ASSISTANT_ID_FILE):
            with open(ASSISTANT_ID_FILE, 'r') as f:
                data = json.load(f)
                self.assistant_id = data.get('assistant_id')
                print(f"✅ Loaded existing assistant: {self.assistant_id}")
                return self.assistant_id
        
        # Create new assistant
        print("🔧 Creating new assistant...")
        try:
            assistant = self.client.beta.assistants.create(
                name="AKS Documentation Expert with Web Search",
                instructions="""You are an expert in AKS (Azure Kubernetes Service) documentation and support. 
                Use the provided documentation AND web search to answer technical questions accurately. 
                ALWAYS include links to the original documentation you referenced in your answer.
                When using web search, prioritize official Microsoft documentation and recent information.
                Be concise but thorough. Format your responses with proper markdown.""",
                model=self.deployment_name,
                tools=[{"type": "file_search"}],
            )
            
            # Update assistant with vector store
            assistant = self.client.beta.assistants.update(
                assistant_id=assistant.id,
                tool_resources={"file_search": {"vector_store_ids": [self.vector_store_id]}}
            )
            
            # Save assistant ID
            with open(ASSISTANT_ID_FILE, "w") as f:
                json.dump({"assistant_id": assistant.id}, f)
            
            self.assistant_id = assistant.id
            print(f"✅ Assistant created: {self.assistant_id}")
            return self.assistant_id
            
        except Exception as e:
            print(f"❌ Failed to create assistant: {e}")
            return None

    # def ask_question(self, question: str) -> None:
    #     """Ask a question to the assistant"""
    #     if not self.thread_id:
    #         thread = self.client.beta.threads.create(
    #             tool_resources={
    #                 "file_search": {
    #                     "vector_store_ids": [self.vector_store_id]
    #                 }
    #             }
    #         )
    #         self.thread_id = thread.id
        
    #     # Add message to thread
    #     self.client.beta.threads.messages.create(
    #         thread_id=self.thread_id,
    #         role="user",
    #         content=question,  
    #     )
        
    #     # Run the assistant
    #     print("🔄 Processing your question...")
    #     run = self.client.beta.threads.runs.create_and_poll(
    #         thread_id=self.thread_id,
    #         assistant_id=self.assistant_id,
    #         instructions="Search through the AKS documentation to answer this question. Cite specific documents you reference.",
    #         tools=[{"type": "file_search"}]
    #     )
        
    #     if run.status == 'completed':
    #         # Get messages
    #         messages = self.client.beta.threads.messages.list(
    #             thread_id=self.thread_id
    #         )
            
    #         # Get the latest assistant message
    #         for message in messages:
    #             if message.role == "assistant":
    #                 for content in message.content:
    #                     if hasattr(content, 'text'):
    #                         text_content = content.text.value
    #                         annotations = getattr(content.text, 'annotations', [])
                            
    #                          # Debug: Print what we're getting
    #                         print(f"DEBUG: Found {len(annotations)} annotations")
    #                         for ann in annotations:
    #                             print(f"DEBUG: Annotation type: {type(ann)}")
    #                             if hasattr(ann, 'file_citation'):
    #                                 print(f"DEBUG: File citation found!")
                
    #                         # Process citations
    #                         final_content = self.process_citations(text_content, annotations)
                            
    #                         print(f"\n🤖 Assistant:\n{final_content}\n")
    #                         return
    #     else:
    #         print(f"❌ Run failed with status: {run.status}")

    def process_citations(self, message_content: str, annotations: List) -> str:
        """Process citations and add proper links using wiki URL mapping"""
        if not annotations:
            return message_content
        
        unique_citations = {}
        citations = []
        
        for index, annotation in enumerate(annotations):
            pattern = re.escape(annotation.text)
            message_content = re.sub(pattern, f" [{index}]", message_content)
            
            if hasattr(annotation, "file_citation"):
                file_citation = annotation.file_citation
                cited_file = self.client.files.retrieve(file_citation.file_id)
                
                # Extract filename
                file_name = cited_file.filename
                display_name = file_name.replace('.md', '')
                
                # Try to get public URL from mapping
                public_url = self.get_public_url(file_name)
                
                # Get quote preview
                quote = getattr(file_citation, "quote", "Document")
                preview_text = quote[:200] + "..." if len(quote) > 200 else quote
                
                # Only add unique citations
                citation_key = file_name  # Use filename as key for uniqueness
                if citation_key not in unique_citations:
                    unique_citations[citation_key] = len(citations)
                    
                    # Create citation with HTML links
                    if public_url:
                        citation_text = f'[{len(citations)}] <a href="{public_url}" target="_blank">{display_name}</a>'
                    else:
                        # Fallback to just the display name without URL
                        citation_text = f"[{len(citations)}] {display_name}"
                    
                    if quote != "Document" and quote:
                        citation_text += f"<br><blockquote>{preview_text}</blockquote>"
                    citations.append(citation_text)
                else:
                    # Replace with existing citation index
                    existing_index = unique_citations[citation_key]
                    message_content = message_content.replace(f"[{index}]", f"[{existing_index}]")
        
        # Add citations at the end with HTML formatting
        if citations:
            message_content += "<br><br><strong>Sources:</strong><br>" + "<br><br>".join(citations)
        
        return message_content

    # def ask_question(self, question: str, return_response: bool = False, stream: bool = False):
    #     """Ask a question to the assistant"""
    #     print(f"🐛 DEBUG: ask_question called with: question='{question}', return_response={return_response}, stream={stream}")
        
    #     if not self.thread_id:
    #         print("🐛 DEBUG: Creating new thread...")
    #         thread = self.client.beta.threads.create(
    #             tool_resources={
    #                 "file_search": {
    #                     "vector_store_ids": [self.vector_store_id]
    #                 }
    #             }
    #         )
    #         self.thread_id = thread.id
    #         print(f"🐛 DEBUG: ✅ Thread created: {self.thread_id}")
    #     else:
    #         print(f"🐛 DEBUG: Using existing thread: {self.thread_id}")
        
    #     # Add message to thread
    #     print("🐛 DEBUG: Adding message to thread...")
    #     self.client.beta.threads.messages.create(
    #         thread_id=self.thread_id,
    #         role="user",
    #         content=question,  
    #     )
    #     print("🐛 DEBUG: ✅ Message added to thread")
        
    #     # Prepare tools list - use bing.definitions like the working wiki_assistant.py
    #     # Prepare tools list - extract the JSON-serializable format
    #     tools = [{"type": "file_search"}]
    #     # if self.bing_tool:
    #     #     try:
    #     #         # The BingGroundingTool.definitions returns a list with the tool definition
    #     #         # Extract the actual dict from the definitions
    #     #         if hasattr(self.bing_tool, 'definitions') and self.bing_tool.definitions:
    #     #             for tool_def in self.bing_tool.definitions:
    #     #                 # Convert to dict if it's not already
    #     #                 if hasattr(tool_def, '__dict__'):
    #     #                     # It's an object, need to convert to dict
    #     #                     tool_dict = {
    #     #                         "type": "bing_grounding",
    #     #                         "bing_grounding": {
    #     #                             "connection_id": os.getenv("AZURE_BING_CONNECTION_ID")
    #     #                         }
    #     #                     }
    #     #                     tools.append(tool_dict)
    #     #                 else:
    #     #                     # It's already a dict
    #     #                     tools.append(tool_def)
    #     #             print(f"🐛 DEBUG: Added Bing grounding tool")
    #     #         else:
    #     #             # Fallback to manual configuration
    #     #             tools.append({
    #     #                 "type": "bing_grounding",
    #     #                 "bing_grounding": {
    #     #                     "connection_id": os.getenv("AZURE_BING_CONNECTION_ID")
    #     #                 }
    #     #             })
    #     #             print("🐛 DEBUG: Added Bing grounding tool (fallback)")
    #     #     except Exception as e:
    #     #         print(f"🐛 DEBUG: Error adding Bing tools: {e}")
    #     #         print("🐛 DEBUG: Continuing without Bing grounding")
    #     # else:
    #     #     print("🐛 DEBUG: No Bing tool available")
    #     print(f"🐛 DEBUG: Final tools array: {tools}")

    #     # Run the assistant with explicit file search
    #     print("🔄 Processing your question...")
    #     print("🐛 DEBUG: About to create assistant run...")
        
    #     if stream:
    #         print("🐛 DEBUG: Creating streaming run...")
    #         try:
    #             run = self.client.beta.threads.runs.create(
    #                 thread_id=self.thread_id,
    #                 assistant_id=self.assistant_id,
    #                 instructions="""You MUST search through the uploaded AKS documentation files to answer this question comprehensively. 

    #     SEARCH PRIORITY:
    #     1. Search the uploaded documentation files for official AKS guidance
    #     2. Use multiple search queries if needed to find comprehensive information
    #     3. Look for related topics and cross-references

    #     CITATION REQUIREMENTS:
    #     - ALWAYS cite specific documents you reference using the file_search tool
    #     - Include proper file names and relevant sections
    #     - Provide clear links to source documentation
    #     - If multiple sources cover the topic, synthesize the information

    #     FORMAT:
    #     - Clear answer with step-by-step guidance
    #     - Include relevant examples and best practices from the documentation""",
    #                 tools=tools,
    #                 stream=True
    #             )
    #             print("🐛 DEBUG: ✅ Streaming run created successfully")
    #         except Exception as e:
    #             print(f"🐛 DEBUG: ❌ Error creating streaming run: {type(e).__name__}: {str(e)}")
    #             raise
            
    #         response_content = ""
    #         print("🐛 DEBUG: Starting to process stream events...")
            
    #         try:
    #             for event in run:
    #                 print(f"🐛 DEBUG: Stream event: {event.event}")
    #                 if event.event == 'thread.message.delta':
    #                     for content in event.data.delta.content:
    #                         if hasattr(content, 'text') and hasattr(content.text, 'value'):
    #                             chunk = content.text.value
    #                             response_content += chunk
    #                             yield chunk
    #                 elif event.event == 'thread.run.completed':
    #                     print("🐛 DEBUG: Run completed, processing citations...")
    #                     # Process final content with citations
    #                     messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
    #                     for message in messages:
    #                         if message.role == "assistant":
    #                             for content in message.content:
    #                                 if hasattr(content, 'text'):
    #                                     text_content = content.text.value
    #                                     annotations = getattr(content.text, 'annotations', [])
    #                                     final_content = self.process_citations(text_content, annotations)
                                        
    #                                     # Send any remaining content
    #                                     if len(final_content) > len(response_content):
    #                                         remaining = final_content[len(response_content):]
    #                                         yield remaining
    #                                     print("🐛 DEBUG: ✅ Streaming response completed")
    #                                     return
    #         except Exception as e:
    #             print(f"🐛 DEBUG: ❌ Error processing stream: {type(e).__name__}: {str(e)}")
    #             raise
    #     else:
    #         print("🐛 DEBUG: Creating non-streaming run...")
    #         try:
    #             run = self.client.beta.threads.runs.create_and_poll(
    #                 thread_id=self.thread_id,
    #                 assistant_id=self.assistant_id,
    #                 instructions="""You MUST search through the uploaded AKS documentation files to answer this question comprehensively. 

    #     SEARCH PRIORITY:
    #     1. Search the uploaded documentation files for official AKS guidance
    #     2. Use multiple search queries if needed to find comprehensive information
    #     3. Look for related topics and cross-references

    #     CITATION REQUIREMENTS:
    #     - ALWAYS cite specific documents you reference using the file_search tool
    #     - Include proper file names and relevant sections
    #     - Provide clear links to source documentation
    #     - If multiple sources cover the topic, synthesize the information

    #     FORMAT:
    #     - Clear answer with step-by-step guidance
    #     - Use HTML links for citations: <a href="URL" target="_blank">Link Text</a>
    #     - Use basic HTML formatting: <strong>bold</strong>, <em>italic</em>, <br> for line breaks
    #     - Include relevant examples and best practices from the documentation
    #     - Do not use markdown - use HTML formatting only""",
    #                 tools=tools,
    #             )
    #             print(f"🐛 DEBUG: ✅ Non-streaming run created with status: {run.status}")
    #         except Exception as e:
    #             print(f"🐛 DEBUG: ❌ Error creating non-streaming run: {type(e).__name__}: {str(e)}")
    #             raise
        
    #     if run.status == 'completed':
    #         print("🐛 DEBUG: Run completed successfully, processing messages...")
    #         # Get messages
    #         messages = self.client.beta.threads.messages.list(
    #             thread_id=self.thread_id
    #         )
    #         for message in messages:
    #             if message.role == "assistant":
    #                 for content in message.content:
    #                     if hasattr(content, 'text'):
    #                         text_content = content.text.value
    #                         annotations = getattr(content.text, 'annotations', [])
                            
    #                         # Process citations
    #                         final_content = self.process_citations(text_content, annotations)
                            
    #                         if return_response:
    #                             print("🐛 DEBUG: ✅ Returning response")
    #                             return final_content
    #                         else:
    #                             print(f"\n🤖 Assistant:\n{final_content}\n")
    #                             print("🐛 DEBUG: ✅ Response printed")
    #                             return final_content
    #     else:
    #         print(f"❌ Run failed with status: {run.status}")
    #         print(f"🐛 DEBUG: ❌ Run failed with status: {run.status}")

    # def ask_question(self, question: str, return_response: bool = False, stream: bool = False):
    #     """
    #     Two-phase approach:
    #     1. gpt-4.1: ONLY retrieves relevant content from vector store with citations
    #     2. gpt-5: Generates the actual answer using retrieved content
    #     """
    #     if not self.assistant:
    #         error_msg = "❌ No assistant available"
    #         print(error_msg)
    #         if stream:
    #             yield error_msg
    #             return
    #         return None
        
    #     # Simple approach: Default to AKS retrieval unless it's clearly a general/personal question
    #     general_keywords = [
    #         'weather', 'time', 'date', 'hello', 'hi', 'how are you', 'good morning', 
    #         'good afternoon', 'good evening', 'what are you', 'who are you', 
    #         'knowledge cutoff', 'what model', 'what version'
    #     ]
        
    #     is_general_question = any(keyword in question.lower() for keyword in general_keywords)
        
    #     print(f"🐛 DEBUG: Question: '{question[:100]}...'")
    #     print(f"🐛 DEBUG: is_general_question: {is_general_question}")
        
    #     if is_general_question:
    #         print("🐛 DEBUG: General question detected, using direct gpt-5...")
    #         try:
    #             if stream:
    #                 comp = self.client.chat.completions.create(
    #                     model=self.generation_model,
    #                     messages=[
    #                         {"role": "system", "content": "Answer the question directly and accurately."},
    #                         {"role": "user", "content": question}
    #                     ],
    #                     # max_completion_tokens=800,
    #                     stream=True
    #                 )
    #                 for chunk in comp:
    #                     if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content:
    #                         yield chunk.choices[0].delta.content
    #                 return
    #             else:
    #                 comp = self.client.chat.completions.create(
    #                     model=self.generation_model,
    #                     messages=[
    #                         {"role": "system", "content": "Answer the question directly and accurately."},
    #                         {"role": "user", "content": question}
    #                     ],
    #                     # max_completion_tokens=800
    #                 )
    #                 direct_answer = comp.choices[0].message.content
    #                 if return_response:
    #                     return direct_answer
    #                 print(f"\n🤖 Answer (direct gpt-5):")
    #                 print(direct_answer)
    #                 return direct_answer
    #         except Exception as e:
    #             error_msg = f"❌ Direct gpt-5 failed: {e}"
    #             print(error_msg)
    #             if stream:
    #                 yield error_msg
    #                 return
    #             return None

    #     # For all other questions, use AKS retrieval + GPT-5 generation
    #     print("🐛 DEBUG: Using AKS retrieval + GPT-5 generation...")

    #     # Phase 1: Pure retrieval (gpt-4.1 as retrieval engine)
    #     # Don't yield process messages for streaming - only print them
    #     print("🔍 Searching AKS documentation...")
        
    #     if not self.thread_id:
    #         print("🐛 DEBUG: Creating new thread...")
    #         thread = self.client.beta.threads.create(
    #             tool_resources={
    #                 "file_search": {
    #                     "vector_store_ids": [self.vector_store_id]
    #                 }
    #             }
    #         )
    #         self.thread_id = thread.id
    #         print(f"🐛 DEBUG: ✅ Thread created: {self.thread_id}")

    #     print("🐛 DEBUG: Adding message to thread...")
    #     self.client.beta.threads.messages.create(
    #         thread_id=self.thread_id,
    #         role="user",
    #         content=question
    #     )

    #     # Create run with RETRIEVAL-FOCUSED instructions
    #     print("🐛 DEBUG: Creating retrieval run...")
    #     run = self.client.beta.threads.runs.create(
    #         thread_id=self.thread_id,
    #         assistant_id=self.assistant.id,
    #         instructions="""You are a RETRIEVAL assistant. Your job is to find and cite relevant content from the AKS documentation.

    # RETRIEVAL INSTRUCTIONS:
    # 1. Use file_search extensively to find ALL relevant information
    # 2. ALWAYS include citations with file names
    # 3. Provide comprehensive content - don't summarize or shorten
    # 4. Include multiple sources if they contain relevant information
    # 5. Your response should be raw retrieval content with citations, not a polished answer

    # Format your response as:
    # - Raw content from documents
    # - Clear citations: [filename.md] or similar
    # - Multiple sections if relevant""",
    #         tools=[{"type": "file_search"}],
    #     )
    #     print(f"🐛 DEBUG: Initial run status={run.status} run_id={run.id}")

    #     # Poll for completion
    #     while True:
    #         run = self.client.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run.id)
    #         print(f"🐛 DEBUG: Poll run status={run.status}")
    #         if run.status in ["completed", "failed", "cancelled"]:
    #             break
    #         if getattr(run, 'required_action', None):
    #             print(f"🐛 DEBUG: Run requires action: {run.required_action}")
    #             if stream:
    #                 yield f"❌ Run requires action: {run.required_action}"
    #                 return
    #             return None
    #         time.sleep(1)

    #     if run.status != "completed":
    #         err = getattr(run, "last_error", None)
    #         error_msg = f"❌ Retrieval run failed status={run.status} last_error={err}"
    #         print(error_msg)
    #         if stream:
    #             yield error_msg
    #             return
    #         return None

    #     # Extract retrieved content
    #     print("🐛 DEBUG: Extracting retrieved content...")
    #     messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
    #     print(f"🐛 DEBUG: Found {len(messages.data)} messages")
        
    #     retrieved_content = ""
    #     citations = []
        
    #     for m in messages.data:
    #         print(f"🐛 DEBUG: Message role={m.role}, content_count={len(m.content)}")
    #         if m.role == "assistant":
    #             for i, c in enumerate(m.content):
    #                 print(f"🐛 DEBUG: Content {i} type={type(c)}, has_text={hasattr(c, 'text')}")
    #                 if hasattr(c, "text"):
    #                     text_value = getattr(c.text, "value", "")
    #                     annotations = getattr(c.text, "annotations", [])
    #                     print(f"🐛 DEBUG: Text length={len(text_value)}, annotations={len(annotations)}")
    #                     if text_value:
    #                         retrieved_content = text_value
    #                         citations = annotations
    #                         print(f"🐛 DEBUG: ✅ Extracted {len(retrieved_content)} chars, {len(citations)} citations")
    #                         break
    #             if retrieved_content:
    #                 break
        
    #     if not retrieved_content:
    #         fallback_msg = "❌ No content retrieved from vector store, using direct gpt-5..."
    #         print(fallback_msg)
            
    #         try:
    #             if stream:
    #                 comp = self.client.chat.completions.create(
    #                     model=self.generation_model,
    #                     messages=[
    #                         {"role": "system", "content": "You are an Azure Kubernetes Service expert. Answer the question using your knowledge of AKS and Kubernetes."},
    #                         {"role": "user", "content": question}
    #                     ],
    #                     # max_completion_tokens=800,
    #                     stream=True
    #                 )
    #                 for chunk in comp:
    #                     if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content:
    #                         yield chunk.choices[0].delta.content
    #                 return
    #             else:
    #                 comp = self.client.chat.completions.create(
    #                     model=self.generation_model,
    #                     messages=[
    #                         {"role": "system", "content": "Answer the question directly and accurately."},
    #                         {"role": "user", "content": question}
    #                     ],
    #                     # max_completion_tokens=800
    #                 )
    #                 direct_answer = comp.choices[0].message.content
    #                 print(f"\n🤖 Answer (direct gpt-5):")
    #                 print(direct_answer)
    #                 return direct_answer if return_response else direct_answer
    #         except Exception as e:
    #             error_msg = f"❌ Direct gpt-5 failed: {e}"
    #             print(error_msg)
    #             if stream:
    #                 yield error_msg
    #                 return
    #             return None

    #     # Process citations from retrieval
    #     print(f"🐛 DEBUG: Processing {len(citations)} citations...")
    #     retrieved_with_citations = self.process_citations(retrieved_content, citations)

    #     # Don't yield process messages for streaming - only print them
    #     print("📝 Generating comprehensive response...")

    #     # Phase 2: gpt-5 generates final answer using retrieved content
    #     print(f"🐛 DEBUG: Generating final answer with gpt-5...")
    #     try:
    #         final_prompt = f"""You are an expert on Azure Kubernetes Service. Answer the following question using ONLY the provided retrieved content. Do not add information not found in the retrieved content.

    # QUESTION: {question}

    # RETRIEVED CONTENT WITH CITATIONS:
    # {retrieved_with_citations}

    # INSTRUCTIONS:
    # - Provide a clear, comprehensive answer
    # - Maintain all citations from the retrieved content
    # - Structure the response for readability
    # - Do not add facts not present in the retrieved content
    # - If the retrieved content doesn't fully answer the question, acknowledge what information is available"""

    #         if stream:
    #             comp = self.client.chat.completions.create(
    #                 model=self.generation_model,
    #                 messages=[
    #                     {"role": "system", "content": "You are an AKS expert. Answer using only the provided retrieved content."},
    #                     {"role": "user", "content": final_prompt}
    #                 ],
    #                 # max_completion_tokens=1200,
    #                 stream=True
    #             )
    #             for chunk in comp:
    #                 if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content:
    #                     yield chunk.choices[0].delta.content
    #             print(f"🐛 DEBUG: ✅ Generated streaming answer with gpt-5")
    #             return
    #         else:
    #             comp = self.client.chat.completions.create(
    #                 model=self.generation_model,
    #                 messages=[
    #                     {"role": "system", "content": "You are an AKS expert. Answer using only the provided retrieved content."},
    #                     {"role": "user", "content": final_prompt}
    #                 ]
    #                 # max_completion_tokens=1200
    #             )
    #             final_answer = comp.choices[0].message.content
    #             print(f"🐛 DEBUG: ✅ Generated final answer with gpt-5")
                
    #             if return_response:
    #                 return final_answer

    #             print(f"\n🤖 Answer (gpt-5 with retrieved context):")
    #             print(final_answer)
    #             return final_answer
                
    #     except Exception as e:
    #         error_msg = f"⚠️ gpt-5 generation failed, returning raw retrieved content: {e}"
    #         print(error_msg)
    #         if stream:
    #             yield f"\n\n⚠️ Generation failed, here's the raw retrieved content:\n\n{retrieved_with_citations}"
    #             return
    #         return retrieved_with_citations

    def ask_question(self, question: str, return_response: bool = False, stream: bool = False):
        """
        Two-phase approach:
        1. gpt-4.1: ONLY retrieves relevant content from vector store with citations
        2. gpt-5: Generates the actual answer using retrieved content
        
        ALL questions go through AKS retrieval - no routing logic.
        """
        if not self.assistant:
            error_msg = "❌ No assistant available"
            print(error_msg)
            if stream:
                yield error_msg
                return
            return None

        # ALL questions use AKS retrieval + GPT-5 generation
        print("🐛 DEBUG: Using AKS retrieval + GPT-5 generation for all questions...")

        # Phase 1: Pure retrieval (gpt-4.1 as retrieval engine)
        # Don't yield process messages for streaming - only print them
        print("🔍 Searching AKS documentation...")
        
        if not self.thread_id:
            print("🐛 DEBUG: Creating new thread...")
            thread = self.client.beta.threads.create(
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [self.vector_store_id]
                    }
                }
            )
            self.thread_id = thread.id
            print(f"🐛 DEBUG: ✅ Thread created: {self.thread_id}")

        print("🐛 DEBUG: Adding message to thread...")
        self.client.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=question
        )

        # Create run with RETRIEVAL-FOCUSED instructions
        print("🐛 DEBUG: Creating retrieval run...")
        run = self.client.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant.id,
            instructions="""You are a RETRIEVAL assistant. Your job is to find and cite relevant content from the AKS documentation.

RETRIEVAL INSTRUCTIONS:
1. Use file_search extensively to find ALL relevant information
2. ALWAYS include citations with file names
3. Provide comprehensive content - don't summarize or shorten
4. Include multiple sources if they contain relevant information
5. Your response should be raw retrieval content with citations, not a polished answer

Format your response as:
- Raw content from documents
- Clear citations: [filename.md] or similar
- Multiple sections if relevant""",
            tools=[{"type": "file_search"}],
        )
        print(f"🐛 DEBUG: Initial run status={run.status} run_id={run.id}")

        # Poll for completion
        while True:
            run = self.client.beta.threads.runs.retrieve(thread_id=self.thread_id, run_id=run.id)
            print(f"🐛 DEBUG: Poll run status={run.status}")
            if run.status in ["completed", "failed", "cancelled"]:
                break
            if getattr(run, 'required_action', None):
                print(f"🐛 DEBUG: Run requires action: {run.required_action}")
                if stream:
                    yield f"❌ Run requires action: {run.required_action}"
                    return
                return None
            time.sleep(1)

        if run.status != "completed":
            err = getattr(run, "last_error", None)
            error_msg = f"❌ Retrieval run failed status={run.status} last_error={err}"
            print(error_msg)
            if stream:
                yield error_msg
                return
            return None

        # Extract retrieved content
        print("🐛 DEBUG: Extracting retrieved content...")
        messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
        
        print(f"🐛 DEBUG: Found {len(messages.data)} messages")
        retrieved_content = ""
        citations = []
        
        for message in messages.data:
            print(f"🐛 DEBUG: Message role={message.role}, content_count={len(message.content)}")
            if message.role == "assistant":
                for i, content in enumerate(message.content):
                    print(f"🐛 DEBUG: Content {i} type={type(content)}, has_text={hasattr(content, 'text')}")
                    if hasattr(content, 'text'):
                        text_content = content.text.value
                        annotations = getattr(content.text, 'annotations', [])
                        print(f"🐛 DEBUG: Text length={len(text_content)}, annotations={len(annotations)}")
                        
                        if text_content:
                            retrieved_content = text_content
                            citations = annotations
                            print(f"🐛 DEBUG: ✅ Extracted {len(text_content)} chars, {len(citations)} citations")
                            break
                if retrieved_content:
                    break

        print(f"🐛 DEBUG: Processing {len(citations)} citations...")
        processed_content = self.process_citations(retrieved_content, citations) if citations else retrieved_content

        # Phase 2: Generation (gpt-5 synthesis)
        print("📝 Generating comprehensive response...")
        
        generation_prompt = f"""Based on the retrieved AKS documentation content below, provide a comprehensive and helpful answer to the user's question.

RETRIEVED CONTENT:
{processed_content}

USER QUESTION:
{question}

INSTRUCTIONS:
- Use the retrieved content as your primary source
- If the retrieved content is relevant, synthesize it into a clear, helpful answer
- If the retrieved content is not relevant to the question, acknowledge this and provide a general helpful response
- Maintain any citations from the retrieved content
- Be conversational and helpful
- Include specific examples and guidance when available from the documentation"""

        print("🐛 DEBUG: Generating final answer with gpt-5...")
        try:
            if stream:
                comp = self.client.chat.completions.create(
                    model=self.generation_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful AKS assistant. Use the provided retrieved content to answer questions accurately."},
                        {"role": "user", "content": generation_prompt}
                    ],
                    max_completion_tokens=800,  # Required for GPT-5
                    stream=True
                )
                for chunk in comp:
                    if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                print("🐛 DEBUG: ✅ Generated streaming answer with gpt-5")
                return
            else:
                comp = self.client.chat.completions.create(
                    model=self.generation_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful AKS assistant. Use the provided retrieved content to answer questions accurately."},
                        {"role": "user", "content": generation_prompt}
                    ],
                    max_completion_tokens=800  # Required for GPT-5
                )
                final_answer = comp.choices[0].message.content
                print("🐛 DEBUG: ✅ Generated non-streaming answer with gpt-5")
                
                if return_response:
                    return final_answer
                print(f"\n🤖 Final Answer:")
                print(final_answer)
                return final_answer
                
        except Exception as e:
            error_msg = f"❌ GPT-5 generation failed: {e}"
            print(error_msg)
            if stream:
                yield error_msg
                return
            return None
    def interactive_mode(self) -> None:
        """Interactive question-answer mode"""
        print("\n💬 Interactive mode - Type 'exit' to quit\n")
        
        while True:
            question = input("You: ").strip()
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye!")
                break
            
            if question:
                self.ask_question(question)

    def delete_vector_store(self) -> None:
        """Delete the vector store completely"""
        # Try to load from file if not already loaded
        if not self.vector_store_id and os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                self.vector_store_id = data.get('vector_store_id')
        
        if not self.vector_store_id:
            print("❌ No vector store found to delete")
            return
        
        print(f"\n⚠️  WARNING: About to delete vector store: {self.vector_store_id}")
        confirm = input("Are you sure? This cannot be undone. Type 'yes' to confirm: ")
        
        if confirm.lower() != 'yes':
            print("❌ Deletion cancelled")
            return
        
        try:
            # Delete the vector store
            self.client.beta.vector_stores.delete(self.vector_store_id)
            print(f"✅ Vector store {self.vector_store_id} deleted successfully")
            
            # Remove the saved file
            if os.path.exists(VECTOR_STORE_FILE):
                os.remove(VECTOR_STORE_FILE)
                print("✅ Removed vector store ID file")
            
            # Also delete the assistant since it references this vector store
            if os.path.exists(ASSISTANT_ID_FILE):
                with open(ASSISTANT_ID_FILE, 'r') as f:
                    assistant_id = json.load(f).get('assistant_id')
                
                if assistant_id:
                    try:
                        self.client.beta.assistants.delete(assistant_id)
                        print(f"✅ Deleted assistant {assistant_id}")
                    except Exception as e:
                        print(f"⚠️  Could not delete assistant: {e}")
                
                os.remove(ASSISTANT_ID_FILE)
                print("✅ Removed assistant ID file")
            
            self.vector_store_id = None
            self.assistant_id = None
            
        except Exception as e:
            print(f"❌ Error deleting vector store: {e}")
    
    def download_ado_wiki(self, organization: str, project: str, wiki_name: str, 
                      pat: str, subpage_path: str, save_dir: str) -> None:
        """Download ADO wiki pages with proper hierarchy and progress tracking"""
        import base64
        import requests
        import time
        
        print(f"\n📥 Starting ADO Wiki Download")
        print(f"=" * 50)
        print(f"📌 Organization: {organization}")
        print(f"📌 Project: {project}")
        print(f"📌 Wiki: {wiki_name}")
        print(f"📌 Subpath: {subpage_path}")
        print(f"📌 Save to: {save_dir}")
        print(f"=" * 50)
        
        # Base URLs
        base_url = f"https://dev.azure.com/{organization}/{project}/_apis/wiki/wikis/{wiki_name}"
        web_url = f"https://dev.azure.com/{organization}/{project}/_wiki/wikis/{wiki_name}"
        auth = base64.b64encode(f":{pat}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}

        os.makedirs(save_dir, exist_ok=True)
        
        # Fetch the full wiki page tree
        print("\n🔍 Fetching wiki structure...")
        start_time = time.time()
        
        try:
            response = requests.get(
                f"{base_url}/pages?path=/&recursionLevel=Full&api-version=7.1",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            print(f"✅ Wiki structure fetched in {time.time() - start_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to fetch wiki structure: {e}")
            return

        # Handle different response formats
        if "value" in data:
            all_pages = data["value"]
        else:
            all_pages = self.flatten_pages(data)

        print(f"📊 Total pages in wiki: {len(all_pages)}")

        subpage_path = subpage_path.strip("/")
        filtered_pages = [
            p for p in all_pages
            if p.get("gitItemPath", "").startswith(f"/{subpage_path}")
        ]

        if not filtered_pages:
            print(f"❌ No pages found under '{subpage_path}'.")
            return

        print(f"📄 Found {len(filtered_pages)} pages under /{subpage_path}")
        
        # Track statistics
        success_count = 0
        error_count = 0
        total_size = 0
        error_pages = []
        
        # Process each filtered wiki page
        print(f"\n⬇️  Downloading pages...")
        download_start = time.time()
        
        for i, page in enumerate(filtered_pages):
            path = page.get("path", "")
            
            # Show progress every 10 pages or for first/last 5
            if i < 5 or i >= len(filtered_pages) - 5 or (i + 1) % 10 == 0:
                print(f"\n[{i+1}/{len(filtered_pages)}] Processing: {path}")
            
            encoded_path = requests.utils.quote(path, safe="")

            try:
                # Get the content for this page
                content_response = requests.get(
                    f"{base_url}/pages?path={encoded_path}&includeContent=true&api-version=7.1-preview.1",
                    headers=headers
                )
                content_response.raise_for_status()
                
                content_data = content_response.json()
                content = content_data.get("content", "")
                
                # Show content size
                content_size = len(content.encode('utf-8'))
                total_size += content_size
                
                if i < 5 or i >= len(filtered_pages) - 5 or (i + 1) % 10 == 0:
                    print(f"    📝 Content size: {content_size:,} bytes")

                # Generate the live wiki URL for this page
                wiki_page_url = f"{web_url}/?pagePath={encoded_path}"
                modified_content = f"[View this page online]({wiki_page_url})\n\n{content}"

                # Create proper directory structure
                relative_path = path[len(f"/{subpage_path}"):].lstrip('/')
                
                if relative_path:
                    file_dir = os.path.join(save_dir, os.path.dirname(relative_path))
                    os.makedirs(file_dir, exist_ok=True)
                    filename = os.path.join(save_dir, f"{relative_path}.md")
                else:
                    filename = os.path.join(save_dir, f"{subpage_path}.md")

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(modified_content)
                
                if i < 5 or i >= len(filtered_pages) - 5 or (i + 1) % 10 == 0:
                    print(f"    ✅ Saved to: {os.path.relpath(filename, save_dir)}")
                
                success_count += 1
                
            except requests.exceptions.HTTPError as e:
                error_count += 1
                error_pages.append((path, str(e)))
                if i < 5 or i >= len(filtered_pages) - 5 or (i + 1) % 10 == 0:
                    print(f"    ❌ Error: {e}")
            except Exception as e:
                error_count += 1
                error_pages.append((path, str(e)))
                if i < 5 or i >= len(filtered_pages) - 5 or (i + 1) % 10 == 0:
                    print(f"    ❌ Unexpected error: {e}")
            
            # Show progress bar every 50 pages
            if (i + 1) % 50 == 0:
                progress = (i + 1) / len(filtered_pages) * 100
                elapsed = time.time() - download_start
                rate = (i + 1) / elapsed
                eta = (len(filtered_pages) - i - 1) / rate if rate > 0 else 0
                
                print(f"\n📊 Progress: {progress:.1f}% | "
                    f"Speed: {rate:.1f} pages/s | "
                    f"ETA: {eta:.0f}s | "
                    f"Success: {success_count} | "
                    f"Errors: {error_count}")

        # Final summary
        download_time = time.time() - download_start
        print(f"\n{'='*50}")
        print(f"✅ Download Complete!")
        print(f"{'='*50}")
        print(f"📊 Summary:")
        print(f"   • Total pages processed: {len(filtered_pages)}")
        print(f"   • Successfully downloaded: {success_count}")
        print(f"   • Failed: {error_count}")
        print(f"   • Total size: {total_size / 1024 / 1024:.2f} MB")
        print(f"   • Time taken: {download_time:.1f}s")
        print(f"   • Average speed: {len(filtered_pages) / download_time:.1f} pages/s")
        print(f"   • Saved to: {os.path.abspath(save_dir)}")
        
        if error_pages:
            print(f"\n⚠️  Failed pages:")
            for page, error in error_pages[:5]:  # Show first 5 errors
                print(f"   • {page}: {error}")
            if len(error_pages) > 5:
                print(f"   ... and {len(error_pages) - 5} more errors")
        
        # Check directory structure
        print(f"\n📁 Directory structure created:")
        for root, dirs, files in os.walk(save_dir):
            level = root.replace(save_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            
            # Show first few files in each directory
            for i, file in enumerate(files[:3]):
                print(f"{subindent}{file}")
            if len(files) > 3:
                print(f"{subindent}... and {len(files) - 3} more files")
            
            # Only show first 5 directories
            if level == 0 and len(dirs) > 5:
                for dir in dirs[:5]:
                    print(f"{indent}  {dir}/")
                print(f"{indent}  ... and {len(dirs) - 5} more directories")
                break

    def flatten_pages(self, page):
        """Helper for download_ado_wiki"""
        pages = []
        if "subPages" in page and page["subPages"]:
            for sub in page["subPages"]:
                pages.append(sub)
                pages.extend(self.flatten_pages(sub))
        return pages
    
    def download_ado_wiki_incremental(self, organization: str, project: str, wiki_name: str, 
                                 pat: str, subpage_path: str, save_dir: str) -> None:
        """Download ADO wiki pages incrementally, skipping unchanged files and updating changed ones"""
        # Track what's already downloaded with checksums
        downloaded_files_log = os.path.join(save_dir, "download_progress.json")
        downloaded_files = {}  # Changed to dict to store checksums
        
        # Load existing progress
        if os.path.exists(downloaded_files_log):
            with open(downloaded_files_log, 'r') as f:
                progress_data = json.load(f)
                downloaded_files = progress_data.get('downloaded_files', {})
                print(f"📋 Found existing progress: {len(downloaded_files)} files already tracked")
        
        print(f"\n📥 Starting Incremental ADO Wiki Download")
        print(f"=" * 50)
        print(f"📌 Organization: {organization}")
        print(f"📌 Project: {project}")
        print(f"📌 Wiki: {wiki_name}")
        print(f"📌 Subpath: {subpage_path}")
        print(f"📌 Save to: {save_dir}")
        print(f"=" * 50)
        
        # Base URLs
        base_url = f"https://dev.azure.com/{organization}/{project}/_apis/wiki/wikis/{wiki_name}"
        web_url = f"https://dev.azure.com/{organization}/{project}/_wiki/wikis/{wiki_name}"
        auth = base64.b64encode(f":{pat}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}

        os.makedirs(save_dir, exist_ok=True)
        
        # Fetch the full wiki page tree
        print("\n🔍 Fetching wiki structure...")
        start_time = time.time()
        
        try:
            response = requests.get(
                f"{base_url}/pages?path=/&recursionLevel=Full&api-version=7.1",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            print(f"✅ Wiki structure fetched in {time.time() - start_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to fetch wiki structure: {e}")
            return

        # Handle different response formats
        if "value" in data:
            all_pages = data["value"]
        else:
            all_pages = self.flatten_pages(data)

        print(f"📊 Total pages in wiki: {len(all_pages)}")

        subpage_path = subpage_path.strip("/")
        filtered_pages = [
            p for p in all_pages
            if p.get("gitItemPath", "").startswith(f"/{subpage_path}")
        ]

        if not filtered_pages:
            print(f"❌ No pages found under '{subpage_path}'.")
            return

        # Analyze what needs to be downloaded/updated
        pages_to_download = []
        pages_to_update = []
        unchanged_pages = []
        
        print(f"\n🔍 Analyzing changes...")
        
        for i, page in enumerate(filtered_pages):
            path = page.get("path", "")
            
            # Show progress for analysis
            if (i + 1) % 1000 == 0:
                print(f"  Analyzed {i + 1}/{len(filtered_pages)} pages...")
            
            # Get page content to check if it's changed
            encoded_path = requests.utils.quote(path, safe="")
            try:
                content_response = requests.get(
                    f"{base_url}/pages?path={encoded_path}&includeContent=true&api-version=7.1-preview.1",
                    headers=headers
                )
                content_response.raise_for_status()
                content_data = content_response.json()
                content = content_data.get("content", "")
                
                # Calculate content hash
                content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                
                # Check if we have this file and if it's changed
                if path not in downloaded_files:
                    pages_to_download.append((page, content, content_hash))
                elif downloaded_files[path] != content_hash:
                    pages_to_update.append((page, content, content_hash))
                else:
                    unchanged_pages.append(path)
                    
            except Exception as e:
                # If we can't get content, assume we need to download
                pages_to_download.append((page, None, None))
        
        print(f"\n📊 Analysis Results:")
        print(f"📄 Total pages under /{subpage_path}: {len(filtered_pages)}")
        print(f"✅ Unchanged: {len(unchanged_pages)}")
        print(f"🆕 New to download: {len(pages_to_download)}")
        print(f"🔄 Changed to update: {len(pages_to_update)}")
        
        all_pages_to_process = pages_to_download + pages_to_update
        
        if not all_pages_to_process:
            print("🎉 All pages are up to date!")
            return
        
        # Track statistics
        success_count = 0
        error_count = 0
        total_size = 0
        error_pages = []
        
        # Process pages that need downloading/updating
        print(f"\n⬇️  Processing {len(all_pages_to_process)} pages...")
        download_start = time.time()
        
        for i, (page, content, content_hash) in enumerate(all_pages_to_process):
            path = page.get("path", "")
            is_update = path in downloaded_files
            
            # Show progress every 10 pages or for first/last 5
            if i < 5 or i >= len(all_pages_to_process) - 5 or (i + 1) % 10 == 0:
                action = "🔄 Updating" if is_update else "🆕 Downloading"
                print(f"\n[{i+1}/{len(all_pages_to_process)}] {action}: {path}")
            
            try:
                # If we don't have content yet, fetch it
                if content is None:
                    encoded_path = requests.utils.quote(path, safe="")
                    content_response = requests.get(
                        f"{base_url}/pages?path={encoded_path}&includeContent=true&api-version=7.1-preview.1",
                        headers=headers
                    )
                    content_response.raise_for_status()
                    content_data = content_response.json()
                    content = content_data.get("content", "")
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                
                # Show content size
                content_size = len(content.encode('utf-8'))
                total_size += content_size
                
                if i < 5 or i >= len(all_pages_to_process) - 5 or (i + 1) % 10 == 0:
                    print(f"    📝 Content size: {content_size:,} bytes")

                # Generate the live wiki URL for this page
                encoded_path = requests.utils.quote(path, safe="")
                wiki_page_url = f"{web_url}/?pagePath={encoded_path}"

                # Resolve user GUIDs in the content if we have a PAT
                if pat:  # We have PAT available, so resolve GUIDs
                    content = self.resolve_ado_user_guids(content, organization, pat)

                modified_content = f"[View this page online]({wiki_page_url})\n\n{content}"

                # Create proper directory structure
                relative_path = path[len(f"/{subpage_path}"):].lstrip('/')
                
                if relative_path:
                    file_dir = os.path.join(save_dir, os.path.dirname(relative_path))
                    os.makedirs(file_dir, exist_ok=True)
                    filename = os.path.join(save_dir, f"{relative_path}.md")
                else:
                    filename = os.path.join(save_dir, f"{subpage_path}.md")

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(modified_content)
                
                if i < 5 or i >= len(all_pages_to_process) - 5 or (i + 1) % 10 == 0:
                    print(f"    ✅ Saved to: {os.path.relpath(filename, save_dir)}")
                
                success_count += 1
                downloaded_files[path] = content_hash
                
                # Save progress every 10 files
                if (i + 1) % 10 == 0:
                    with open(downloaded_files_log, 'w') as f:
                        json.dump({
                            'downloaded_files': downloaded_files,
                            'last_updated': time.time(),
                            'total_tracked': len(downloaded_files),
                            'last_session_stats': {
                                'new': len(pages_to_download),
                                'updated': len(pages_to_update),
                                'unchanged': len(unchanged_pages)
                            }
                        }, f)
                    
            except Exception as e:
                error_count += 1
                error_pages.append((path, str(e)))
                if i < 5 or i >= len(all_pages_to_process) - 5 or (i + 1) % 10 == 0:
                    print(f"    ❌ Error: {e}")
            
            # Show progress bar every 50 pages
            if (i + 1) % 50 == 0:
                progress = (i + 1) / len(all_pages_to_process) * 100
                elapsed = time.time() - download_start
                rate = (i + 1) / elapsed
                eta = (len(all_pages_to_process) - i - 1) / rate if rate > 0 else 0
                
                print(f"\n📊 Progress: {progress:.1f}% | "
                    f"Speed: {rate:.1f} pages/s | "
                    f"ETA: {eta:.0f}s | "
                    f"Success: {success_count} | "
                    f"Errors: {error_count}")

        # Save final progress
        with open(downloaded_files_log, 'w') as f:
            json.dump({
                'downloaded_files': downloaded_files,
                'last_updated': time.time(),
                'total_tracked': len(downloaded_files),
                'completed': True,
                'last_session_stats': {
                    'new': len(pages_to_download),
                    'updated': len(pages_to_update),
                    'unchanged': len(unchanged_pages)
                }
            }, f)

        # Final summary
        download_time = time.time() - download_start
        print(f"\n{'='*50}")
        print(f"✅ Incremental Sync Complete!")
        print(f"{'='*50}")
        print(f"📊 Summary:")
        print(f"   • New pages downloaded: {len(pages_to_download)}")
        print(f"   • Pages updated: {len(pages_to_update)}")
        print(f"   • Unchanged pages: {len(unchanged_pages)}")
        print(f"   • Successfully processed: {success_count}")
        print(f"   • Failed: {error_count}")
        print(f"   • Total pages tracked: {len(downloaded_files)}")
        print(f"   • Total size this session: {total_size / 1024 / 1024:.2f} MB")
        print(f"   • Time taken: {download_time:.1f}s")
        print(f"   • Average speed: {len(all_pages_to_process) / download_time:.1f} pages/s" if download_time > 0 else "")
        print(f"   • Saved to: {os.path.abspath(save_dir)}")

    def check_download_status(self, save_dir: str) -> None:
        """Check what's been downloaded and what's missing"""
        downloaded_files_log = os.path.join(save_dir, "download_progress.json")
        
        if not os.path.exists(downloaded_files_log):
            print("❌ No download progress found. Run --download first.")
            return
        
        with open(downloaded_files_log, 'r') as f:
            progress_data = json.load(f)
        
        downloaded_files = progress_data.get('downloaded_files', {})
        last_updated = progress_data.get('last_updated', 0)
        completed = progress_data.get('completed', False)
        last_session = progress_data.get('last_session_stats', {})
        
        print(f"\n📊 Download Status Report")
        print(f"=" * 40)
        print(f"📁 Directory: {save_dir}")
        print(f"📄 Files tracked: {len(downloaded_files)}")
        print(f"📅 Last updated: {time.ctime(last_updated) if last_updated else 'Unknown'}")
        print(f"✅ Completed: {'Yes' if completed else 'No'}")
        
        if last_session:
            print(f"\n📈 Last Session:")
            print(f"   🆕 New downloads: {last_session.get('new', 0)}")
            print(f"   🔄 Updates: {last_session.get('updated', 0)}")
            print(f"   ✅ Unchanged: {last_session.get('unchanged', 0)}")
        
        # Count actual files on disk
        actual_files = 0
        if os.path.exists(save_dir):
            for root, dirs, files in os.walk(save_dir):
                actual_files += len([f for f in files if f.endswith('.md')])
        
        print(f"💾 Files on disk: {actual_files}")
        
        if actual_files != len(downloaded_files):
            print(f"⚠️  Mismatch detected! Progress log shows {len(downloaded_files)} but found {actual_files} files")


    def rebuild_progress_from_existing_files(self, save_dir: str = "./downloaded_wiki/AKS") -> None:
        """Rebuild progress log by scanning existing downloaded files"""
        downloaded_files_log = os.path.join(save_dir, "download_progress.json")
        
        print(f"\n🔧 Rebuilding progress log from existing files...")
        print(f"📁 Scanning directory: {save_dir}")
        
        if not os.path.exists(save_dir):
            print(f"❌ Directory {save_dir} doesn't exist")
            return
        
        # Scan all existing .md files
        existing_files = []
        for root, dirs, files in os.walk(save_dir):
            for file in files:
                if file.endswith('.md') and file != 'download_progress.json':
                    file_path = os.path.join(root, file)
                    existing_files.append(file_path)
        
        print(f"📄 Found {len(existing_files)} markdown files on disk")
        
        # Build progress tracking with dummy hashes (we'll calculate real ones on next download)
        downloaded_files = {}
        
        print(f"🔍 Mapping files to ADO paths...")
        
        for i, file_path in enumerate(existing_files):
            # Show progress
            if (i + 1) % 1000 == 0 or i < 10:
                print(f"  Processing {i + 1}/{len(existing_files)}: {os.path.basename(file_path)}")
            
            try:
                # Convert file path back to ADO wiki path
                relative_path = os.path.relpath(file_path, save_dir)
                # Remove .md extension
                relative_path = relative_path[:-3] if relative_path.endswith('.md') else relative_path
                # Convert to ADO path format
                if relative_path == "AKS":
                    ado_path = "/AKS"
                else:
                    ado_path = f"/AKS/{relative_path}".replace(os.sep, '/')
                
                # Use dummy hash - will be updated on next download if content changed
                downloaded_files[ado_path] = "existing_file"
                
            except Exception as e:
                print(f"    ❌ Error processing {file_path}: {e}")
        
        # Save the rebuilt progress
        progress_data = {
            'downloaded_files': downloaded_files,
            'last_updated': time.time(),
            'total_tracked': len(downloaded_files),
            'completed': True,
            'rebuilt_from_existing': True,
            'rebuild_timestamp': time.time(),
            'files_found_on_disk': len(existing_files)
        }
        
        with open(downloaded_files_log, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        print(f"\n✅ Progress log rebuilt successfully!")
        print(f"📊 Summary:")
        print(f"   • Files on disk: {len(existing_files)}")
        print(f"   • Files mapped to ADO paths: {len(downloaded_files)}")
        print(f"   • Progress log saved to: {downloaded_files_log}")
        print(f"\n💡 You can now run --download to sync any new/changed files")

    def resolve_ado_user_guids(self, content: str, organization: str, pat: str, cache: Dict[str, str] = None) -> str:
        """Resolve ADO user GUIDs in content to display names using the ADO API"""
        if cache is None:
            cache = {}
        
        # Pattern to match ADO user GUIDs: @<GUID>
        guid_pattern = r'@<([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})>'
        
        guids = re.findall(guid_pattern, content, re.IGNORECASE)
        if not guids:
            return content
        
        auth = base64.b64encode(f":{pat}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        
        # Process each unique GUID
        for guid in set(guids):  # Use set to avoid duplicate API calls
            if guid in cache:
                # Use cached result
                display_name = cache[guid]
            else:
                # Look up the user via ADO API
                display_name = self._lookup_ado_user(organization, guid, headers)
                cache[guid] = display_name
            
            # Replace all occurrences of this GUID with the display name
            guid_pattern_specific = f'@<{guid}>'
            if display_name and display_name != 'Unknown User':
                replacement = f"@{display_name}"
            else:
                # Keep original if we couldn't resolve it
                replacement = f"@<{guid}>"
            
            content = content.replace(guid_pattern_specific, replacement)
        
        return content

    def _lookup_ado_user(self, organization: str, user_guid: str, headers: Dict[str, str]) -> str:
        """Look up a single user GUID and return their display name"""
        try:
            # Use the working vssps identities API
            url = f"https://vssps.dev.azure.com/{organization}/_apis/identities/{user_guid}?api-version=7.1"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                # Extract the display name from providerDisplayName field
                display_name = user_data.get('providerDisplayName', 'Unknown User')
                return display_name
            else:
                print(f"  ⚠️  Could not resolve user {user_guid}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  ⚠️  Could not resolve user {user_guid}: {e}")
        
        return 'Unknown User'

    def resolve_guids_in_existing_files(self, organization: str, pat: str, wiki_dir: str) -> None:
        """Process existing downloaded wiki files to resolve user GUIDs"""
        print(f"\n🔄 Resolving user GUIDs in existing files...")
        print(f"📂 Directory: {wiki_dir}")
        
        if not os.path.exists(wiki_dir):
            print(f"❌ Directory {wiki_dir} does not exist")
            return
        
        # Count total markdown files
        total_files = 0
        for root, dirs, files in os.walk(wiki_dir):
            total_files += sum(1 for file in files if file.endswith('.md'))
        
        print(f"📊 Found {total_files} markdown files to process")
        
        if total_files == 0:
            print("ℹ️  No markdown files found")
            return
        
        # Shared cache for user GUID lookups
        user_cache = {}
        files_processed = 0
        files_modified = 0
        total_guids_resolved = 0
        
        for root, dirs, files in os.walk(wiki_dir):
            for file in files:
                if file.endswith('.md'):
                    files_processed += 1
                    file_path = os.path.join(root, file)
                    
                    try:
                        # Read the file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            original_content = f.read()
                        
                        # Count GUIDs in this file
                        guid_pattern = r'@<([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})>'
                        guids_in_file = re.findall(guid_pattern, original_content, re.IGNORECASE)
                        
                        if guids_in_file:
                            # Resolve GUIDs in content
                            modified_content = self.resolve_ado_user_guids(
                                original_content, organization, pat, user_cache
                            )
                            
                            # Only write back if content actually changed
                            if modified_content != original_content:
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(modified_content)
                                
                                files_modified += 1
                                unique_guids = len(set(guids_in_file))
                                total_guids_resolved += unique_guids
                                
                                relative_path = os.path.relpath(file_path, wiki_dir)
                                print(f"  ✅ [{files_processed}/{total_files}] {relative_path} - resolved {unique_guids} user(s)")
                        
                        # Show progress for files without GUIDs too
                        elif files_processed % 50 == 0:
                            relative_path = os.path.relpath(file_path, wiki_dir)
                            print(f"  📄 [{files_processed}/{total_files}] {relative_path} - no GUIDs")
                            
                    except Exception as e:
                        relative_path = os.path.relpath(file_path, wiki_dir)
                        print(f"  ❌ Error processing {relative_path}: {e}")
        
        print(f"\n✅ GUID Resolution Complete!")
        print(f"📊 Files processed: {files_processed}")
        print(f"📝 Files modified: {files_modified}")
        print(f"👥 Unique users resolved: {len(user_cache)}")
        print(f"🔗 Total GUID references resolved: {total_guids_resolved}")
        
        if user_cache:
            print(f"\n👥 Resolved Users:")
            for guid, name in sorted(user_cache.items(), key=lambda x: x[1]):
                print(f"  {name} ({guid})")

    def create_test_vector_store(self, wiki_path: str, max_files: int = 10, subpath: str = "AKS") -> str:
        """Create a test vector store with just the first few files for testing"""
        print(f"\n🧪 Creating TEST vector store with max {max_files} files...")
        print(f"📁 Processing wiki files from: {wiki_path}")
        
        # Look for the downloaded wiki directory
        if not os.path.exists(wiki_path):
            print(f"❌ Wiki path not found at {wiki_path}")
            return None
        
        # Test connection first
        print("🔌 Testing Azure OpenAI connection...")
        try:
            test_response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": "test"}]
                # max_tokens=10
            )
            print("✅ Connection to Azure OpenAI successful")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return None

        # Create new vector store for testing
        print("📦 Creating TEST vector store...")
        try:
            vector_store = self.client.beta.vector_stores.create(name="AKSWikiKnowledge_TEST")
            self.vector_store_id = vector_store.id
            
            # Save vector store ID with test suffix
            test_vector_file = "test_vector_store_id.json"
            with open(test_vector_file, "w") as f:
                json.dump({"vector_store_id": vector_store.id}, f)
            print(f"💾 TEST Vector store created: {self.vector_store_id}")
            
        except Exception as e:
            print(f"❌ Failed to create vector store: {e}")
            return None

        # Collect files to upload (preserving hierarchy)
        files_to_upload = []
        file_count = 0
        
        # Walk through the directory and collect files with their relative paths
        for root, dirs, files in os.walk(wiki_path):
            # Sort directories and files for consistent ordering
            dirs.sort()
            files.sort()
            
            for file in files:
                if file.endswith('.md') and file != 'download_progress.json':
                    if file_count >= max_files:
                        break
                        
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, wiki_path)
                    
                    files_to_upload.append({
                        'path': file_path,
                        'relative_path': relative_path,
                        'size': os.path.getsize(file_path)
                    })
                    file_count += 1
                    
            if file_count >= max_files:
                break
        
        print(f"\n📊 Selected {len(files_to_upload)} files for testing:")
        total_size = 0
        for i, file_info in enumerate(files_to_upload, 1):
            size_mb = file_info['size'] / 1024 / 1024
            total_size += file_info['size']
            print(f"  {i:2d}. {file_info['relative_path']} ({size_mb:.2f} MB)")
        
        print(f"\n📈 Total size: {total_size / 1024 / 1024:.2f} MB")
        
        # Confirm before uploading
        confirm = input(f"\n❓ Upload these {len(files_to_upload)} files to test vector store? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Upload cancelled")
            return None
        
        # Upload files in batches
        print(f"\n📤 Uploading {len(files_to_upload)} files...")
        batch_size = 111  # Smaller batches for testing
        
        for i in range(0, len(files_to_upload), batch_size):
            batch = files_to_upload[i:i + batch_size]
            batch_files = [file_info['path'] for file_info in batch]
            
            print(f"\n  📦 Batch {i//batch_size + 1}: uploading {len(batch)} files...")
            for file_info in batch:
                print(f"    📄 {file_info['relative_path']}")
            
            self._upload_batch(vector_store.id, batch_files, i + 1, i + len(batch))
        
        print(f"\n✅ TEST vector store setup complete!")
        print(f"🆔 Vector Store ID: {self.vector_store_id}")
        print(f"💾 Saved to: test_vector_store_id.json")
        
        return self.vector_store_id

    def create_or_load_test_assistant(self) -> str:
        """Create or load test assistant"""
        print(f"\n🤖 Setting up TEST AI assistant...")
        
        test_assistant_file = "test_assistant_id.json"
        
        # Check if test assistant already exists
        if os.path.exists(test_assistant_file):
            with open(test_assistant_file, 'r') as f:
                data = json.load(f)
                self.assistant_id = data.get('assistant_id')
                print(f"✅ Loaded existing TEST assistant: {self.assistant_id}")
                return self.assistant_id
        
        # Create new test assistant
        print("🔧 Creating new TEST assistant...")
        try:
            assistant = self.client.beta.assistants.create(
                name="AKS Documentation Expert (TEST)",
                instructions="""You are an expert in AKS (Azure Kubernetes Service) documentation. 
                This is a TEST environment with limited documentation.
                Use the provided documentation to answer technical questions accurately. 
                ALWAYS include the link to the original documentation you referenced in your answer.
                Be concise but thorough. Format your responses with proper markdown.
                Note: This is working with a limited test dataset.""",
                model=self.deployment_name,
                tools=[{"type": "file_search"}],
            )
            
            # Update assistant with vector store
            assistant = self.client.beta.assistants.update(
                assistant_id=assistant.id,
                tool_resources={"file_search": {"vector_store_ids": [self.vector_store_id]}}
            )
            
            # Save test assistant ID
            with open(test_assistant_file, "w") as f:
                json.dump({"assistant_id": assistant.id}, f)
            
            self.assistant_id = assistant.id
            print(f"✅ TEST Assistant created: {self.assistant_id}")
            return self.assistant_id
            
        except Exception as e:
            print(f"❌ Failed to create TEST assistant: {e}")
            return None

    def cleanup_test_resources(self) -> None:
        """Clean up test vector store and assistant"""
        print(f"\n🧹 Cleaning up TEST resources...")
        
        # Load test resources
        test_vector_file = "test_vector_store_id.json"
        test_assistant_file = "test_assistant_id.json"
        
        # Delete test vector store
        if os.path.exists(test_vector_file):
            with open(test_vector_file, 'r') as f:
                data = json.load(f)
                vector_store_id = data.get('vector_store_id')
            
            if vector_store_id:
                try:
                    self.client.beta.vector_stores.delete(vector_store_id)
                    print(f"✅ Deleted TEST vector store: {vector_store_id}")
                except Exception as e:
                    print(f"❌ Error deleting TEST vector store: {e}")
            
            os.remove(test_vector_file)
            print("✅ Removed test vector store file")
        
        # Delete test assistant
        if os.path.exists(test_assistant_file):
            with open(test_assistant_file, 'r') as f:
                data = json.load(f)
                assistant_id = data.get('assistant_id')
            
            if assistant_id:
                try:
                    self.client.beta.assistants.delete(assistant_id)
                    print(f"✅ Deleted TEST assistant: {assistant_id}")
                except Exception as e:
                    print(f"❌ Error deleting TEST assistant: {e}")
            
            os.remove(test_assistant_file)
            print("✅ Removed test assistant file")
        
        print(f"🎉 TEST cleanup complete!")

    def peek_test_vector_store(self) -> None:
        """Peek at files in the test vector store"""
        test_vector_file = "test_vector_store_id.json"
        
        if not os.path.exists(test_vector_file):
            print("❌ No test vector store found. Run --test-setup first.")
            return
        
        with open(test_vector_file, 'r') as f:
            data = json.load(f)
            vector_store_id = data.get('vector_store_id')
        
        if not vector_store_id:
            print("❌ No test vector store ID found")
            return
        
        print(f"\n👀 Peeking into TEST vector store: {vector_store_id}")
        
        try:
            # List files in the vector store
            files = self.client.beta.vector_stores.files.list(
                vector_store_id=vector_store_id,
                limit=100  # Show more files for testing
            )
            
            print(f"\n📄 Files in test vector store ({len(files.data)} files):\n")
            for i, file in enumerate(files.data):
                print(f"{i+1}. File ID: {file.id}")
                
                # Retrieve file details
                file_details = self.client.files.retrieve(file.id)
                print(f"   Name: {file_details.filename}")
                print(f"   Size: {file_details.bytes} bytes")
                print(f"   Status: {getattr(file, 'status', 'unknown')}")
                
                # Try to get content preview for the first few files
                if i < 3:
                    try:
                        content = self.client.files.content(file.id)
                        preview = content.read().decode('utf-8')[:300] + "..."
                        print(f"   Preview: {preview}\n")
                    except Exception as e:
                        print(f"   Preview: Not available ({e})\n")
                else:
                    print()
                    
        except Exception as e:
            print(f"❌ Error peeking into vector store: {e}")

    def test_vector_store_search(self, query: str) -> None:
        """Test search functionality in the test vector store"""
        test_vector_file = "test_vector_store_id.json"
        test_assistant_file = "test_assistant_id.json"
        
        if not os.path.exists(test_vector_file) or not os.path.exists(test_assistant_file):
            print("❌ Test resources not found. Run --test-setup first.")
            return
        
        with open(test_vector_file, 'r') as f:
            vector_store_id = json.load(f).get('vector_store_id')
        
        with open(test_assistant_file, 'r') as f:
            assistant_id = json.load(f).get('assistant_id')
        
        print(f"\n🔍 Testing search in vector store: {vector_store_id}")
        print(f"🤖 Using assistant: {assistant_id}")
        print(f"🔎 Query: {query}")
        
        try:
            # Create a test thread
            thread = self.client.beta.threads.create(
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [vector_store_id]
                    }
                }
            )
            
            # Add the query
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Search for: {query}. Please show what documents you found and quote the exact text.",
            )
            
            # Run with detailed instructions
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=assistant_id,
                instructions="""Search through the uploaded documents for the user's query. 
                ALWAYS cite the specific documents you found.
                Quote the exact text from the documents.
                If you can't find the information, say so explicitly.""",
                tools=[{"type": "file_search"}]
            )
            
            if run.status == 'completed':
                messages = self.client.beta.threads.messages.list(thread_id=thread.id)
                
                for message in messages:
                    if message.role == "assistant":
                        for content in message.content:
                            if hasattr(content, 'text'):
                                text_content = content.text.value
                                annotations = getattr(content.text, 'annotations', [])
                                
                                print(f"\n🤖 Search Results:")
                                print(f"📄 Found {len(annotations)} citations")
                                
                                # Process and show citations
                                final_content = self.process_citations(text_content, annotations)
                                print(f"\n{final_content}")
                                return
            else:
                print(f"❌ Search failed with status: {run.status}")
                
        except Exception as e:
            print(f"❌ Error during search test: {e}")

    def count_test_vector_store_files(self) -> None:
        """Count the true total number of files in the test vector store"""
        test_vector_file = "test_vector_store_id.json"
        
        if not os.path.exists(test_vector_file):
            print("❌ No test vector store found. Run --test-setup first.")
            return
        
        with open(test_vector_file, 'r') as f:
            data = json.load(f)
            vector_store_id = data.get('vector_store_id')
        
        if not vector_store_id:
            print("❌ No test vector store ID found")
            return
        
        print(f"\n🔢 Counting files in TEST vector store: {vector_store_id}")
        
        try:
            # Get all files by iterating through pages
            all_files = []
            after = None
            
            while True:
                # List files with pagination
                kwargs = {
                    'vector_store_id': vector_store_id,
                    'limit': 100
                }
                if after:
                    kwargs['after'] = after
                
                files_page = self.client.beta.vector_stores.files.list(**kwargs)
                all_files.extend(files_page.data)
                
                # Check if there are more files
                if not files_page.has_more:
                    break
                
                # Get the last file ID for pagination
                if files_page.data:
                    after = files_page.data[-1].id
                else:
                    break
            
            print(f"\n📊 Total files in test vector store: {len(all_files)}")
            
            # Show status breakdown
            status_counts = {}
            for file in all_files:
                status = getattr(file, 'status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            if status_counts:
                print(f"\n📈 Status breakdown:")
                for status, count in status_counts.items():
                    print(f"   {status}: {count} files")
                    
        except Exception as e:
            print(f"❌ Error counting files in vector store: {e}")

    # Add this new method to track uploaded files
    def create_incremental_vector_store(self, wiki_path: str, subpath: str = "AKS") -> str:
        """Create or load vector store with incremental file tracking"""
        print(f"\n🗄️  Setting up incremental vector store...")
        
        # Files to track what's been uploaded
        UPLOADED_FILES_LOG = "uploaded_files.json"
        uploaded_files = {}
        
        # Load existing vector store and uploaded files tracking
        if os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                self.vector_store_id = data.get('vector_store_id')
                
            if os.path.exists(UPLOADED_FILES_LOG):
                with open(UPLOADED_FILES_LOG, 'r') as f:
                    uploaded_files = json.load(f)
            
            print(f"✅ Loaded existing vector store: {self.vector_store_id}")
            print(f"📋 Already uploaded: {len(uploaded_files)} files")
        else:
            # Create new vector store
            print("🔌 Testing Azure OpenAI connection...")
            try:
                test_response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": "test"}]
                    # max_tokens=10
                )
                print("✅ Connection successful")
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return None

            print("📦 Creating new vector store...")
            try:
                vector_store = self.client.beta.vector_stores.create(name="AKSWikiKnowledge")
                self.vector_store_id = vector_store.id
                
                with open(VECTOR_STORE_FILE, "w") as f:
                    json.dump({"vector_store_id": vector_store.id}, f)
                print(f"💾 Vector store created: {self.vector_store_id}")
            except Exception as e:
                print(f"❌ Failed to create vector store: {e}")
                return None

        # Process files incrementally
        print(f"\n🔍 Scanning for new/changed files...")
        
        aks_path = os.path.join(wiki_path, subpath)
        if not os.path.exists(aks_path):
            print(f"❌ Path not found: {aks_path}")
            return None

        new_files = []
        updated_files = []
        unchanged_files = []
        
        for root, dirs, files in os.walk(aks_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, aks_path)
                    
                    # Calculate file hash to detect changes
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                        
                        if relative_path not in uploaded_files:
                            new_files.append((file_path, relative_path, file_hash))
                        elif uploaded_files[relative_path] != file_hash:
                            updated_files.append((file_path, relative_path, file_hash))
                        else:
                            unchanged_files.append(relative_path)
                            
                    except Exception as e:
                        print(f"❌ Error processing {file_path}: {e}")
        
        print(f"\n📊 File Analysis:")
        print(f"   🆕 New files: {len(new_files)}")
        print(f"   🔄 Updated files: {len(updated_files)}")
        print(f"   ✅ Unchanged files: {len(unchanged_files)}")
        
        files_to_upload = new_files + updated_files
        
        if not files_to_upload:
            print("🎉 All files are up to date!")
            return self.vector_store_id
        
        # Upload new/changed files
        print(f"\n📤 Uploading {len(files_to_upload)} files...")
        
        batch_size = 50
        uploaded_count = 0
        
        for i in range(0, len(files_to_upload), batch_size):
            batch = files_to_upload[i:i + batch_size]
            batch_paths = [item[0] for item in batch]
            
            print(f"\n  📦 Batch {i//batch_size + 1}: {len(batch)} files")
            
            # Upload batch
            try:
                file_streams = [open(path, "rb") for path in batch_paths]
                
                file_batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=self.vector_store_id,
                    files=file_streams
                )
                
                print(f"    ✅ Status: {file_batch.status}")
                print(f"    📊 Completed: {file_batch.file_counts.completed}")
                
                # Update tracking for successfully uploaded files
                if file_batch.status == 'completed':
                    for file_path, relative_path, file_hash in batch:
                        uploaded_files[relative_path] = file_hash
                        uploaded_count += 1
                
                # Close file streams
                for f in file_streams:
                    f.close()
                    
            except Exception as e:
                print(f"    ❌ Upload error: {e}")
        
        # Save updated tracking
        with open(UPLOADED_FILES_LOG, 'w') as f:
            json.dump(uploaded_files, f, indent=2)
        
        print(f"\n✅ Incremental upload complete!")
        print(f"   📤 Uploaded: {uploaded_count} files")
        print(f"   📋 Total tracked: {len(uploaded_files)} files")
        
        return self.vector_store_id

    def generate_response(self, question: str, context: str = ""):
        """Generate a streaming response to a question"""
        try:
            # Create a temporary thread for this question
            thread = self.client.beta.threads.create(
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [self.vector_store_id]
                    }
                }
            )
            
            # Add the question with context
            full_question = f"{question}\n\nContext: {context}" if context else question
            
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=full_question
            )
            
            # Run the assistant with streaming
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id,
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
                            yield chunk
                elif event.event == 'thread.run.completed':
                    # Process final content with citations
                    messages = self.client.beta.threads.messages.list(thread_id=thread.id)
                    for message in messages:
                        if message.role == "assistant":
                            for content in message.content:
                                if hasattr(content, 'text'):
                                    text_content = content.text.value
                                    annotations = getattr(content.text, 'annotations', [])
                                    final_content = self.process_citations(text_content, annotations)
                                    
                                    # Send any remaining content
                                    if len(final_content) > len(response_content):
                                        remaining = final_content[len(response_content):]
                                        yield remaining
                                    return
            
        except Exception as e:
            yield f"Error generating response: {str(e)}"
            
    def check_wiki_coverage(self) -> None:
        """Check how much of the eligible wiki content hasn't been scraped"""
        print(f"\n🔍 Checking wiki coverage...")
        
        # Count downloaded files
        downloaded_dir = "./downloaded_wiki/AKS"
        downloaded_count = 0
        downloaded_size = 0
        
        if os.path.exists(downloaded_dir):
            for root, dirs, files in os.walk(downloaded_dir):
                for file in files:
                    if file.endswith('.md'):
                        file_path = os.path.join(root, file)
                        downloaded_count += 1
                        downloaded_size += os.path.getsize(file_path)
        
        print(f"📁 Downloaded files: {downloaded_count}")
        print(f"💾 Downloaded size: {downloaded_size / 1024 / 1024:.2f} MB")
        
        # Check vector store files
        uploaded_files_log = "uploaded_files.json"
        uploaded_count = 0
        
        if os.path.exists(uploaded_files_log):
            with open(uploaded_files_log, 'r') as f:
                uploaded_files = json.load(f)
                uploaded_count = len(uploaded_files)
        
        print(f"☁️  Uploaded to vector store: {uploaded_count}")
        
        # Estimate remaining from ADO (this would require API call)
        print(f"\n💡 To check total available pages, run:")
        print(f"   python3 aks.py --check-ado-total")
        
def main():
    parser = argparse.ArgumentParser(description="AKS Wiki Assistant CLI")
    parser.add_argument("--setup", action="store_true", help="Setup vector store and assistant")
    parser.add_argument("--ask", type=str, help="Ask a single question")
    parser.add_argument("--interactive", action="store_true", help="Interactive Q&A mode")
    parser.add_argument("--wiki-path", type=str, default="./CloudNativeCompute.wiki", 
                       help="Path to cloned wiki repository")
    parser.add_argument("--subpath", type=str, default="AKS", 
                       help="Subpath within wiki to process (default: AKS)")
    parser.add_argument("--peek", action="store_true", help="Peek at vector store contents")
    parser.add_argument("--delete", action="store_true", help="Delete vector store and assistant")
    parser.add_argument("--download", action="store_true", help="Download wiki from ADO")
    # Add a new command to check download status
    parser.add_argument("--check-download", action="store_true", help="Check download progress")
    parser.add_argument("--rebuild-progress", action="store_true", help="Rebuild progress log from existing files")
    parser.add_argument("--resolve-guids", action="store_true", help="Resolve user GUIDs in existing downloaded files")
    # New test commands
    parser.add_argument("--test-setup", action="store_true", help="Setup TEST vector store with limited files")
    parser.add_argument("--test-files", type=int, default=10, help="Number of files for test setup (default: 10)")
    parser.add_argument("--test-ask", type=str, help="Ask a question using TEST assistant")
    parser.add_argument("--test-interactive", action="store_true", help="Interactive mode with TEST assistant")
    parser.add_argument("--cleanup-test", action="store_true", help="Clean up TEST resources")
    parser.add_argument("--downloaded-wiki-path", type=str, default="./downloaded_wiki/AKS", 
                       help="Path to downloaded wiki files (default: ./downloaded_wiki/AKS)")
    
    parser.add_argument("--peek-test", action="store_true", help="Peek at test vector store contents")
    parser.add_argument("--test-search", type=str, help="Test search functionality in test vector store")
    # Add to parser arguments:
    parser.add_argument("--check-coverage", action="store_true", help="Check wiki coverage and upload status")
    parser.add_argument("--incremental-setup", action="store_true", help="Setup vector store with incremental upload tracking")
    parser.add_argument("--count-test-files", action="store_true", help="Count total files in test vector store")
    parser.add_argument("--test-response", action="store_true", help="Test AI response against human response")
    parser.add_argument("--question", type=str, help="Question to test")
    parser.add_argument("--human-response", type=str, help="Human response to compare against")
    parser.add_argument("--context", type=str, default="", help="Additional context for the question")
    parser.add_argument("--show-labels", action="store_true", help="Show which response is AI vs human")
    parser.add_argument("--run-evaluation-suite", action="store_true", help="Run full evaluation suite")
    parser.add_argument("--test-cases-file", type=str, default="test_cases.json", help="Path to test cases JSON file")

    args = parser.parse_args()
    
    # Check environment variables
    if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
        print("❌ Please set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables")
        sys.exit(1)
    
    assistant = AKSWikiAssistant()
    

    if args.test_response:
        if not args.question or not args.human_response:
            print("❌ Please provide both --question and --human-response for testing")
            sys.exit(1)
        
        # Load assistant
        if os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                assistant.vector_store_id = data.get('vector_store_id')
        
        if os.path.exists(ASSISTANT_ID_FILE):
            with open(ASSISTANT_ID_FILE, 'r') as f:
                data = json.load(f)
                assistant.assistant_id = data.get('assistant_id')
        
        if not assistant.vector_store_id or not assistant.assistant_id:
            print("❌ Please set up the assistant first with --setup")
            sys.exit(1)
        
        # Run single test
        result = assistant.test_against_human_response(
            question=args.question,
            human_response=args.human_response,
            context=args.context,
            show_labels=args.show_labels
        )
        
        # Print results
        assistant.ai_grader.print_evaluation_summary(result)
        return
    
    if args.run_evaluation_suite:
        # Load assistant
        if os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                assistant.vector_store_id = data.get('vector_store_id')
        
        if os.path.exists(ASSISTANT_ID_FILE):
            with open(ASSISTANT_ID_FILE, 'r') as f:
                data = json.load(f)
                assistant.assistant_id = data.get('assistant_id')
        
        if not assistant.vector_store_id or not assistant.assistant_id:
            print("❌ Please set up the assistant first with --setup")
            sys.exit(1)
        
        assistant.run_evaluation_suite(args.test_cases_file)
        return
    
    # Handle debug commands
    if args.peek_test:
        assistant.peek_test_vector_store()
        return
    
    if args.test_search:
        assistant.test_vector_store_search(args.test_search)
        return
    
    # In main(), replace the setup section with:
    if args.setup or args.ask or args.interactive:
        # Comment out the wiki processing check
        # if not os.path.exists(args.wiki_path):
        #     print(f"❌ Wiki path '{args.wiki_path}' not found.")
        #     print(f"💡 Make sure you've downloaded the wiki first using --download")
        #     sys.exit(1)
        
        # Load vector store from file
        if os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                assistant.vector_store_id = data['vector_store_id']
                print(f"✅ Using existing vector store: {assistant.vector_store_id}")
        else:
            print("❌ No vector store found. Run --setup first.")
            sys.exit(1)
            
        assistant.create_or_load_assistant()
        if not assistant.assistant_id:
            print("❌ Failed to create assistant")
            sys.exit(1)
    
    # Handle test questions
    if args.test_ask or args.test_interactive:
        # Load test assistant
        test_vector_file = "test_vector_store_id.json"
        test_assistant_file = "test_assistant_id.json"
        
        if not os.path.exists(test_vector_file) or not os.path.exists(test_assistant_file):
            print("❌ Test resources not found. Run --test-setup first.")
            sys.exit(1)
        
        with open(test_vector_file, 'r') as f:
            assistant.vector_store_id = json.load(f).get('vector_store_id')
        
        with open(test_assistant_file, 'r') as f:
            assistant.assistant_id = json.load(f).get('assistant_id')
        
        if args.test_ask:
            print("🧪 Using TEST assistant...")
            assistant.ask_question(args.test_ask)
        elif args.test_interactive:
            print("🧪 Using TEST assistant in interactive mode...")
            assistant.interactive_mode()
        return
    
    # Add to command handling:
    if args.check_coverage:
        assistant.check_wiki_coverage()
        return

    if args.incremental_setup:
        assistant.create_incremental_vector_store(args.downloaded_wiki_path)
        if assistant.vector_store_id:
            assistant.create_or_load_assistant()
        return
    
    # Handle test cleanup
    if args.cleanup_test:
        assistant.cleanup_test_resources()
        return
    
    # Handle test setup
    if args.test_setup:
        if not os.path.exists(args.downloaded_wiki_path):
            print(f"❌ Downloaded wiki path '{args.downloaded_wiki_path}' not found.")
            print(f"💡 Make sure you've downloaded the wiki first using --download")
            sys.exit(1)
        
        assistant.create_test_vector_store(args.downloaded_wiki_path, args.test_files)
        if not assistant.vector_store_id:
            print("❌ Failed to create test vector store")
            sys.exit(1)
            
        assistant.create_or_load_test_assistant()
        if not assistant.assistant_id:
            print("❌ Failed to create test assistant")
            sys.exit(1)
        return
    
    # For setup, we need the wiki path
    if args.setup:
        if not os.path.exists(args.wiki_path):
            print(f"❌ Wiki path '{args.wiki_path}' not found.")
            print(f"💡 Make sure you've cloned the wiki repository to this location.")
            sys.exit(1)
        
        assistant.create_or_load_vector_store(args.wiki_path, args.subpath)
        if not assistant.vector_store_id:
            print("❌ Failed to create vector store")
            sys.exit(1)
            
        assistant.create_or_load_assistant()
        if not assistant.assistant_id:
            print("❌ Failed to create assistant")
            sys.exit(1)
    
    
    # In the args handling section:
    if args.delete:
        assistant.delete_vector_store()
        return
    
    if args.count_test_files:
        assistant.count_test_vector_store_files()
        return
    
    # In main():
    if args.download:
        assistant.download_ado_wiki_incremental(  # Changed method name
            organization="msazure",
            project="CloudNativeCompute",
            wiki_name="CloudNativeCompute.wiki",
            pat=os.getenv("AZURE_DEVOPS_PAT", "your_pat_here"),
            subpage_path="/AKS",
            save_dir="./downloaded_wiki/AKS"
        )
        return
    
    if args.resolve_guids:
        assistant.resolve_guids_in_existing_files(
            organization="msazure",
            pat=os.getenv("AZURE_DEVOPS_PAT", "your_pat_here"),
            wiki_dir="./downloaded_wiki/AKS"
        )
        return

    if args.peek:
        # Just load the existing vector store ID
        if os.path.exists(VECTOR_STORE_FILE):
            with open(VECTOR_STORE_FILE, 'r') as f:
                data = json.load(f)
                assistant.vector_store_id = data.get('vector_store_id')
                assistant.peek_vector_store()
        else:
            print("❌ No vector store found. Run --setup first.")
        return

    if args.check_download:
        assistant.check_download_status("./downloaded_wiki/AKS")
        return
    
    if args.rebuild_progress:
        assistant.rebuild_progress_from_existing_files()
        return

    # Handle questions
    if args.ask:
        assistant.ask_question(args.ask)
    elif args.interactive:
        assistant.interactive_mode()
    elif not args.setup:
        print("ℹ️  No action specified. Use --help for options.")
    

if __name__ == "__main__":
    main()