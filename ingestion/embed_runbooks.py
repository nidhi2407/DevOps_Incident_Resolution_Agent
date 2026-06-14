import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# Load runbooks
loader = DirectoryLoader("data/runbooks", glob="*.md", loader_cls=TextLoader)
docs = loader.load()

# Chunk
splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
chunks = splitter.split_documents(docs)

# Embed (free, local model)
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

# Store in ChromaDB
vectordb = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="data/chroma_db"
)

print(f"✅ Indexed {len(chunks)} chunks from {len(docs)} runbooks")