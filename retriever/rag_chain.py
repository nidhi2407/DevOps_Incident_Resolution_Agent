from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
vectordb = Chroma(persist_directory="data/chroma_db", embedding_function=embeddings)

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

prompt = PromptTemplate(
    template="""You are a DevOps incident resolution assistant.
Use the context below to diagnose the issue and provide exact kubectl/Terraform commands.

Context:
{context}

Alert:
{question}

Respond with:
1. Root Cause
2. Confidence (High/Medium/Low)
3. Resolution Commands""",
    input_variables=["context", "question"]
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectordb.as_retriever(search_kwargs={"k": 3}),
    chain_type_kwargs={"prompt": prompt}
)

if __name__ == "__main__":
    alert = "Pod my-app-7f9c6 in namespace prod is showing status crashloopbackoff"
    result = qa_chain.invoke({"query": alert})
    print(result["result"])