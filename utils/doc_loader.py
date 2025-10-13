from langchain.document_loaders import DirectoryLoader
from typing import List
from pathlib import Path
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

DATA_PATH = "D:/AI-LLM/Agents/RAGAgent/data"

def load_docs():
    docs = DirectoryLoader(DATA_PATH, glob="**/*.md", show_progress=True).load()
    return docs

def build_chunks_from_docs(
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    docs = load_docs()  

    # Add metadata to each document
    for d in docs:
        src = Path(d.metadata['source'])
        d.metadata["basename"] = src.name
        
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return text_splitter.split_documents(docs)

if __name__ == "__main__":
    doc_splits = build_chunks_from_docs()
    print(f"Built {len(doc_splits)} chunks from PDFs in {DATA_PATH}")
    
    # Persist to Chroma DB
    Chroma.from_documents(
        documents=doc_splits,
        collection_name="htb_2025",                
        persist_directory="D:/AI-LLM/Agents/RAGAgent/crawled_data_store",  
        embedding=OllamaEmbeddings(model="bge-m3")
    )