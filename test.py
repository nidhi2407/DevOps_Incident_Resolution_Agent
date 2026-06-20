import chromadb
from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()
# Test ChromaDB
client = chromadb.Client()
col = client.create_collection("test")
col.add(documents=["pod crashloopbackoff detected"], ids=["1"])
results = col.query(query_texts=["kubernetes pod crash"], n_results=1)
print("ChromaDB ✅:", results["documents"])

# Test OpenAI
oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
resp = oai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Reply with OK"}]
)
print("OpenAI ✅:", resp.choices[0].message.content)

# Test Kubernetes
from kubernetes import client, config
config.load_kube_config()
v1 = client.CoreV1Api()
pods = v1.list_pod_for_all_namespaces()
print(f"Kubernetes ✅: {len(pods.items)} pods found")

