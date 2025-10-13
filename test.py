from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
from langchain_ollama.embeddings import OllamaEmbeddings

load_dotenv()

google_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
embedding = OllamaEmbeddings(model="nomic-embed-text")
url = "https://www.youtube.com/watch?v=KvUC7bakm-E&t=815s"
question = "Give me a full step-by-step of how to solve the Fluffy challenge in HackTheBox."

# Create a Document from the video URL and question and store it in Chroma vectorstore
with open("gemini_response/fluffy.md", "r", encoding="utf-8") as file:
    content = file.read()
doc = Document(page_content=str(content), metadata={"source": url})
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1000,
    chunk_overlap=200,
)
chunks = text_splitter.split_documents([doc])

vectorstore = Chroma(
    collection_name="genai",
    persist_directory=r"D:\AI-LLM\Agents\RAGAgent\crawl4ai_store",
    embedding_function=embedding 
)

vectorstore.add_documents(chunks)
retriever = vectorstore.as_retriever(search_kwargs={"k": 8})
documents = retriever.invoke(question)

# Use RAG to answer the question based on the retrieved documents
prompt = PromptTemplate(
    template="""You are an assistant for question-answering tasks.\n
    Use the following pieces of retrieved context to answer the question.\n
    If you don't know the answer, just say that you don't know.\n
    Here is the context: {context}\n
    Here is the question: {question}\n
    Provide a conversational answer with a step-by-step guide on how to solve the challenge.
    """,
    input_variables=["context", "question"],
)

rag_chain = prompt | google_llm | StrOutputParser()
response = rag_chain.invoke({"context": documents, "question": question})
print(response)  # Print the final answer