import os
from openai import AzureOpenAI   # note: AzureOpenAI, not OpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2025-04-01-preview",                    # or the API version your tenant uses
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),   # e.g. https://exec-docs-ai-experiments.openai.azure.com
)

resp = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role":"user","content":"what is your latest knowledge cutoff date?"}],
)

print(resp.choices[0].message.content)




