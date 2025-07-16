import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage

# 🔧 Update these values
PROJECT_ENDPOINT = "https://exec-docs-ai-experiments.services.ai.azure.com/api/projects/exec-docs"
MODEL_DEPLOYMENT = "gpt-4o"  # your Foundry-deployed model

# Authenticate with Azure
cred = DefaultAzureCredential()

# 1️⃣ Initialize the Foundry project client
project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=cred)

# 2️⃣ List uploaded datasets (should include template.docx)
print("📄 Uploaded datasets:")
for ds in project.datasets.list():
    print(f"- {ds.name} (id: {ds.id}, status: {ds.status})")
# Note the ID for template.docx and paste it below

# ⚙️ Set your dataset ID here
DATASET_ID = "assistant-98SzBZXKFVEx2JhquUmZcV"

# 3️⃣ Create a chat completions client using Foundry models endpoint
models_endpoint = PROJECT_ENDPOINT.replace("/api/projects/exec-docs", "/models")
chat_client = ChatCompletionsClient(endpoint=models_endpoint, credential=cred)

# 4️⃣ Send your question along with the dataset ID
response = chat_client.complete(
    model=MODEL_DEPLOYMENT,
    messages=[
        SystemMessage(content="You have access to the uploaded template.docx."),
        UserMessage(content="Summarize the guidance in Section 1.2")
    ],
    data_sources=[{"id": DATASET_ID}]
)

# 5️⃣ Print the assistant's response
print("\n✅ Assistant Response:\n")
print(response.choices[0].message.content)
