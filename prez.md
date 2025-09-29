# **🎯 AKS AI Hub Presentation: Complete Execution Guide**

## **Pre-Presentation Setup (5 minutes before)**

### **Screens/Tabs to Have Open:**
1. **VS Code** with aks-ai-hub opened
2. **Terminal** in aks-ai-hub directory
3. **Browser tabs:**
   - http://localhost:5000 (your running app)
   - https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki (ADO wiki)
   - https://portal.azure.com (Azure OpenAI Studio)
   - https://github.com/features/copilot (for reference)
4. **Teams/Zoom** screen sharing ready

### **Commands to Run:**
```bash
cd /home/naman10parikh/NamanCode/aks-ai-hub
source venv/bin/activate  # if you have venv
python app.py  # Start your Flask app
```

# **SECTION 0: The Opening - One Cohesive Story (2-3 mins)**

**Start with your screen OFF - just you talking:**

*"Three weeks ago, I posted a simple question in our Teams channel: 'What workflow is stealing your time?' Within hours, I had 15 replies. Everyone was drowning in the same thing - repetitive, process-heavy work that was keeping them from actual strategic thinking. Customer emails taking 45 minutes to research and respond to. PRDs taking 6 hours to write from scratch. GitHub issues eating entire Friday afternoons.*

*This wasn't news to any of us. AKS is probably the most process-heavy team in Azure - and that's actually our secret weapon. Because every process with clear inputs and outputs can be augmented with AI. Not replaced - augmented. Like Lincoln said, 'Give me six hours to chop down a tree and I'll spend the first four sharpening the axe.' We've been chipping at trees with dull axes for years. Adding more people. Working longer hours. But what if we could sharpen the axe instead?*

*So over one weekend - just 20 hours - I built this."*

**[Screen: Show your running app]**

*"This is an AI hub that handles customer support emails, writes PRDs, and triages GitHub issues. It searches through 7,705 wiki pages in 3 seconds instead of 30 minutes. It's already saving me 5 hours a week. Cost to run? $10 a month. Time to build? One weekend. Technical expertise required? Zero.*

*Here's the plot twist - I'm a PM, not a developer. Six months ago, I couldn't have built any of this. But something fundamental has shifted. Natural language has become the new programming language. GitHub Copilot wrote 90% of this code. I just told it what I wanted in plain English. The lines between PM and developer aren't just blurring - they're becoming irrelevant. We're all builders now.*

*But here's what matters - this isn't about agents for agents' sake. In this age of AI, there's so much noise, so many demos, so much 'look what's possible!' But possibility without purpose is just expensive entertainment. Every agent I built solves a validated problem that real people have every single day. This isn't built to wow you - it's built to be USED by you. Tomorrow. In production.*

*The math is simple: 15 PMs on our team, each losing 3 hours a week to repetitive tasks. That's 2,250 hours a year - an entire FTE worth of strategic work we're not doing. My 20-hour investment this weekend will return 100x in the first year alone. But it's not about the hours saved - it's about what we do with them. More customer conversations. Better products. Actual innovation instead of information retrieval.*

*Today, I'm going to show you exactly how to build this. Not in theory, but in practice. We'll scrape wikis, build AI assistants, create web interfaces - all using GitHub Copilot as our pair programmer. And at the end, you'll have a containerized solution ready to deploy. Because the future isn't about who has the best developers - it's about who can best articulate problems and orchestrate solutions. And as PMs, that's literally our job description.*

*So let me ask you this: What if the only thing standing between you and automating your most painful workflow is simply knowing that you already can?"*

**[Transition to main content]**

*"Let's start by exploring AKS for AI and then going a bit behind the scenes"*

---

## **🎯 SECTION I: Introduction & Context (3 mins)**

### **Screen: Keep the app visible, but bring up VS Code**
**Share VS Code window showing your project structure**

**Point to files as you talk:**
- app.py - "Flask backend that orchestrates everything"
- aks.py - "Core AI assistant logic"
- prd_agent.py - "PRD writing assistant"
- `frontend/` - "React TypeScript UI"

**Key message:** *"What you're seeing is a complete production-ready system. But here's the amazing part - GitHub Copilot wrote about 90% of this code. I just provided the domain knowledge and business requirements."*

**Switch between app and code:**
- "Professional web interface" (show app)
- "Production-quality backend" (show app.py)
- "All generated with AI assistance" (show copilot suggestions in VS Code)

---

## **🔥 SECTION II: The Problem We're Solving (2 mins)**

### **Screen: ADO Wiki (dev.azure.com)**
1. **Navigate to the AKS wiki**: `https://dev.azure.com/msazure/CloudNativeCompute/_wiki/wikis/CloudNativeCompute.wiki`
2. **Show the overwhelming structure** - scroll through the navigation
3. **Point out the numbers**: "7,705+ pages of documentation"

### **Screen: Back to VS Code - show wiki_url_mapping.json**
```bash
# In terminal
wc -l wiki_url_mapping.json
```
**Show the file structure:**
```json
{
  "Azure Monitor Application Monitoring (auto-attach).md": "[View this page online](https://dev.azure.com/msazure/...)",
  "Partner.md": "[View this page online](https://dev.azure.com/msazure/...)"
}
```

**Talking points:**
- "Every single one of these files was scraped and indexed"
- "Customers don't know where to look"
- "Even our team members struggle to find the right information quickly"
- "Manual searching = 30+ minutes, AI search = 3 seconds"

---

## **⚡ SECTION III: Phase 1 - Knowledge Base Creation (8 mins)**

### **A. Scraping ADO Wiki**

**Screen: VS Code - Show scraper code (you might need to show this from a separate script)**
**Open terminal and show:**

```bash
# Show the downloaded wiki
ls -la downloaded_wiki | head -20
echo "Total files downloaded:"
find downloaded_wiki -name "*.md" | wc -l
```

**Create a simple demo script to show how Copilot helped:**

**In VS Code, open a new file and show GitHub Copilot in action:**
1. **Type comment:** `# Script to scrape ADO wiki with authentication`
2. **Let Copilot suggest** (press Tab to accept suggestions)
3. **Show how it completes patterns**

**Key talking points:**
- "I just told Copilot 'I need to scrape ADO wiki with authentication'"
- "It generated the PAT token logic, recursive directory traversal, file filtering"
- "I provided the business requirements, Copilot provided the implementation"

### **B. Creating Vector Store**

**Screen: Azure OpenAI Studio**
1. **Navigate to**: `https://portal.azure.com`
2. **Go to your OpenAI resource**: `exec-docs-ai-experiments`
3. **Show Management → Files**
4. **Point to your vector store**

**Show the configuration in VS Code:**
```python
# Open aks.py and navigate to vector store creation
def create_vector_store(self):
    # Show the vector store creation code around line 500-600
```

**Talking points:**
- "One-time setup, reusable forever"
- "Automatic chunking and embedding"
- "Cost: ~$10 for 7,705 files"

### **C. URL Mapping & Citations**

**Screen: VS Code - Open wiki_url_mapping.json**
**Show the structure:**
```json
{
  "filename.md": "[View this page online](https://dev.azure.com/...)"
}
```

**Back to the app - show a response with citations**
**Point out**: "Every response includes links back to the original source"

---

## **🚀 SECTION IV: Phase 2 - Building AI Assistants (12 mins)**

### **A. The Architecture**

**Screen: Draw on whiteboard or use VS Code to show:**
```
User Question → GPT-4.1 (Retrieval) → Vector Store → GPT-5 (Generation) → Response
```

**Screen: VS Code - Open aks.py and show the two-model setup:**
```python
# Navigate to around line 50-100 where models are configured
RETRIEVAL_ASSISTANT_MODEL=gpt-4.1  # from .env
AZURE_OPENAI_MODEL_EMAIL=gpt-5     # from .env
```

### **B. Two-Model Strategy Deep Dive**

**Screen: VS Code - Show the ask_question method (around line 800-1000)**
```python
def ask_question(self, question: str, stream: bool = False):
    # Show the retrieval + generation pattern
```

**Screen: Azure OpenAI Studio**
1. **Show your assistants** in the management portal
2. **Point to the configuration**
3. **Show the tools enabled**: File Search, Bing Grounding

**Talking points:**
- "GPT-4.1 is the retrieval specialist - it knows how to search"
- "GPT-5 is the generation expert - latest model with best reasoning"
- "Each optimized for their specific task"

### **C. Assistant Components**

**Screen: VS Code - Open assistant_id.json and vector_store_id.json**
```json
{"assistant_id": "asst_xyz123"}
{"vector_store_id": "vs_HwOePtkbPqEAWyIyKvJIVq1l"}
```

**Screen: Azure OpenAI Studio - Show the actual assistant configuration**
1. **Navigate to your assistant**
2. **Show the system prompt**
3. **Show the tools configuration**

### **D. Tool Integration**

**Screen: VS Code - Show aks.py around line 30-50 where tools are configured**
```python
def get_bing_grounding_tool():
    connection_name = os.getenv("AZURE_BING_CONNECTION_ID")
    if connection_name:
        tool = BingGroundingTool(connection_id=connection_name)
```

**Screen: .env file - Show configuration (but hide API keys)**
```bash
# Show relevant env vars
grep -E "(BING|MODEL)" .env
```

---

## **💻 SECTION V: Phase 3 - From CLI to Web App (8 mins)**

### **A. Starting with CLI Tool**

**Screen: Terminal**
```bash
# Show the CLI in action
python3 aks.py --ask "How do I scale an AKS cluster?"
```

**Let this run and show the streaming output**

**Talking points:**
- "Started with CLI to prove the concept"
- "Validated the core AI functionality first"
- "Then added the web interface"

### **B. Building the Web Interface**

**Screen: VS Code - Split view showing backend and frontend**

**Left panel: app.py - Show Flask routes:**
```python
@app.route('/api/generate-response', methods=['POST'])
def generate_response():
    # Show the streaming logic
```

**Right panel: frontend/src/App.tsx - Show React structure:**
```tsx
function App() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  // Show the agent selection logic
```

**Screen: Browser - Show the live app**
1. **Navigate through the UI**
2. **Show agent selection**
3. **Show real-time streaming**

### **C. The Power of GitHub Copilot**

**Screen: VS Code - Live demo of Copilot**
1. **Open a new file**
2. **Type**: `// Create a Flask server with Server-Sent Events for real-time streaming`
3. **Show Copilot suggestions**
4. **Accept and iterate**

**Show different Copilot modes:**
- **Inline suggestions**: Start typing a function
- **Chat mode**: Ctrl+Shift+I, ask "How do I add CORS to Flask?"
- **Agent mode**: `@workspace convert this CLI to web API`

**Screen: Show actual Copilot interactions from your history**
*(You can show the command palette or recent copilot chats)*

---

## **🎪 SECTION VI: GitHub Copilot Deep Dive (6 mins)**

### **A. Different Modes Demo**

**Screen: VS Code with Copilot enabled**

**Live demonstrations:**
1. **Inline Suggestions**: 
   - Type: `def create_email_parser(`
   - Show how Copilot completes the function signature and body

2. **Chat Mode**: 
   - Open Copilot chat (Ctrl+Shift+I)
   - Ask: "How do I handle streaming responses in Flask?"
   - Show the response and how you can iterate

3. **Agent Mode**:
   - Type: `@workspace explain the architecture of this AKS assistant`
   - Show how it understands your entire codebase

### **B. Model Selection Strategy**

**Screen: Copilot Settings (VS Code)**
**Show available models:**
- GPT-4o: "Best for complex logic, architecture decisions"
- Claude 3.5 Sonnet: "Excellent for refactoring, code review"  
- o1-preview: "Complex reasoning, algorithm design"

**Talk about cost:** "~$10/month for individual use - less than one hour of contractor time"

### **C. Best Practices Demo**

**Screen: VS Code - Show examples of good vs bad prompts**

**Good prompt example:**
```
// Create a Flask endpoint that:
// 1. Accepts email text via POST
// 2. Extracts the main question using regex patterns
// 3. Returns JSON with question and context
// 4. Handles errors gracefully
```

**Show how Copilot responds better with context and specific requirements**

---

## **🔒 SECTION VII: Security & Deployment (4 mins)**

### **Screen: VS Code - Show .env file (carefully)**
```bash
# Show structure without revealing keys
head -5 .env
```

**Point out the security practices:**
- .env file not committed (show `.gitignore`)
- Environment variables for all secrets
- Azure Key Vault for production

### **Screen: Show Dockerfile**
```dockerfile
# Show the multi-stage build process
# Point out security best practices
```

**Screen: Azure portal (if you have it deployed)**
- Show Container Apps or App Service
- Point out managed identity usage
- Network security settings

---

## **🎬 SECTION VIII: Live Demo Spectacular (10 mins)**

### **Demo 1: Email Support Agent**

**Screen: Your app - AKS Support Assistant**

**Prepare 2-3 different customer emails:**

**Email 1** (Simple):
```
Hi, my AKS cluster is failing to pull images. Getting ImagePullBackOff errors. How do I fix this?
```

**Email 2** (Complex):
```
We're running a microservices architecture on AKS with 200+ services. We're seeing intermittent DNS resolution failures that cause cascading failures across services. Our monitoring shows timeouts happening roughly every 10 minutes. We've already increased resource limits but the issue persists. This is affecting our production workload serving 1M+ users.
```

**For each email:**
1. **Paste into the app**
2. **Show the parsing** ("Extract Question" button)
3. **Generate response** - let it stream
4. **Point out citations**
5. **Show the terminal logs** (retrieval vs generation phases)

### **Demo 2: PRD Builder Agent**

**Screen: Your app - PRD Agent**

**Example requirement:**
```
We need to implement auto-scaling for AKS node pools based on custom metrics like queue length and response time, not just CPU/memory. This should integrate with our existing monitoring stack (Prometheus + Grafana) and support multiple scaling policies per application.
```

**Show:**
1. **Input the requirement**
2. **Generate PRD sections**
3. **Export to Word document**
4. **Open the generated Word doc**

### **Behind the Scenes**

**Screen: Terminal with debug output**
```bash
# Show logs with verbose output
export DEBUG=1
python app.py
```

**Point out:**
- Retrieval phase: "Searching vector store..."
- Generation phase: "Synthesizing response..."
- Token usage and timing

---

## **🛠 SECTION IX: You Can Build This Too! (4 mins)**

### **Screen: GitHub Copilot pricing page**
**Show the costs:**
- Free for students/OSS maintainers
- $10/month individual
- $19/month business

### **Screen: Azure OpenAI portal**
**Show how to request access:** `aka.ms/oai/access`

### **Screen: VS Code Extensions**
**Show the essential setup:**
- GitHub Copilot extension
- GitHub Copilot Chat extension

### **Project Ideas for PMs**

**Screen: Create a quick mockup or whiteboard:**
- Customer feedback analyzer
- Meeting notes summarizer  
- Competitive analysis tool
- Sprint planning assistant
- Release notes generator

**Time Investment Reality Check:**
- Day 1: Tool setup, data preparation (4 hours)
- Day 2-3: Core functionality (8 hours)  
- Day 4-5: Web interface (8 hours)
- **Total: ~20 hours over a weekend**

---

## **🎯 SECTION X: Key Takeaways & Q&A (5 mins)**

### **Screen: Back to your running app**
**Final demo**: Show both agents working seamlessly

### **Key Messages** (write these on screen or have ready):
1. **AI coding is accessible** - GitHub Copilot democratizes development
2. **Start simple** - CLI first, then add complexity  
3. **Leverage existing tools** - Don't reinvent the wheel
4. **PMs can build** - You don't need to be a developer
5. **ROI is massive** - 20 hours of work → hundreds of hours saved

### **Call to Action**
*"Pick one repetitive task you do weekly. Spend next weekend building an AI solution. Share what you build with the team."*

### **Resources to Share**
**Screen: Browser tabs with these open:**
- GitHub Copilot documentation
- Azure OpenAI playground
- Your GitHub repo (if shareable)
- Microsoft Learn AI courses

---

## **🎪 Advanced Demo Ideas (If Time Permits)**

### **Live Coding with Copilot**
**Screen: VS Code - New file**
Start building a new agent live:
```python
# Create an agent that analyzes GitHub issues and suggests labels
```
Show how Copilot helps build it in real-time

### **Performance Analysis**
**Screen: Terminal + Browser DevTools**
Show network timing, response sizes, cost analysis

### **Integration Demo**
Show how this could integrate with Teams, Slack, or other tools

---

## **🚨 Troubleshooting Guide**

### **If the app doesn't work:**
1. Check .env file is loaded
2. Verify OpenAI API key is valid
3. Check vector store and assistant IDs exist
4. Have backup screenshots/recordings

### **If Copilot isn't working:**
1. Check VS Code extension is enabled
2. Verify you're logged into GitHub
3. Have code examples ready to show

### **If demos fail:**
1. Have backup videos/screenshots
2. Show the code instead of live running
3. Focus on the architecture and learnings

---

## **🎬 Presentation Flow Summary**

**Total time: 45-60 minutes**
1. **Business hook** (5) - Show working product first
2. **Problem/solution** (5) - ADO wiki complexity 
3. **Knowledge base** (8) - Scraping + vector store
4. **AI assistants** (12) - Two-model architecture
5. **Web app** (8) - CLI to production app
6. **Copilot deep dive** (6) - Live coding demos
7. **Security/deployment** (4) - Production considerations
8. **Live demo** (10) - Multiple agents working
9. **Build your own** (4) - Getting started guide
10. **Q&A** (3-8) - Flexible based on questions
