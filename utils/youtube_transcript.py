from youtube_transcript_api import YouTubeTranscriptApi
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

llm = ChatOllama(
    model="llama3.1:8b-instruct-q4_0",
    temperature=0.2,     # low temperature for editing tasks, higher for creative tasks
    num_ctx=8192,        # increase if your model supports it
)

to_text = StrOutputParser()

# ---------- 1) Fetch transcript ----------
ytt_api = YouTubeTranscriptApi()
# Each item: {"text": "...", "start": float, "duration": float}
fetched_transcript = ytt_api.fetch("KvUC7bakm-E", languages=["en"])  # or fetch(...)

# Optional: quick guard for empty transcripts
if not fetched_transcript:
    raise RuntimeError("No transcript found for video KvUC7bakm-E")

# ---------- 2) Prepare raw text & docs ----------
# Keep timestamps in metadata for traceability; also build a raw text blob
docs_raw = []
raw_lines = []
for snip in fetched_transcript:
    text = (snip.text or "").strip()
    if not text:
        continue
    docs_raw.append(
        Document(
            page_content=text,
            metadata={"start": snip.start, "duration": snip.duration}
        )
    )
    raw_lines.append(text)

raw_text = "\n".join(raw_lines)

# # ---------- 4) Prompts ----------
map_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a careful editor. Clean up an automatic speech transcript so it's accurate and easy to use for retrieval.\n"
     "Rules:\n"
     "- Fix punctuation, casing, and obvious ASR errors.\n"
     "- Keep meaning faithful; do not hallucinate facts.\n"
     "- Remove disfluencies like 'um', 'uh', repeated words, and obvious filler.\n"
     "- Keep technical terms and proper nouns when confident.\n"
     "- Remove stage notes like [Music], [Applause], unless contentful.\n"
     "- Do not add headings or summaries—return only the refined text.\n"),
    ("user", "Transcript chunk:\n```{chunk}```\nReturn ONLY the refined text.")
])

reduce_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Combine and lightly polish the already-refined chunks into a coherent transcript.\n"
     "Do not summarize; preserve all details. Fix any residual grammar/punctuation issues.\n"
     "Return only the final transcript text."),
    ("user", "Refined chunks:\n```{joined}```")
])

to_text = StrOutputParser()

map_chain = map_prompt | llm | to_text
reduce_chain = reduce_prompt | llm | to_text

# # ---------- 5) Chunk for refinement (map) ----------
# # Use slightly smaller chunks for editing than for retrieval to keep prompts snappy.
refine_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000, chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "]
)
refine_chunks = refine_splitter.split_text(raw_text)

# # Run the map step
refined_chunks = [map_chain.invoke({"chunk": ch}) for ch in refine_chunks]

# # ---------- 6) Light reduce step ----------
# # If the transcript is short, this is trivial; for long transcripts it smooths boundaries.
refined_full = reduce_chain.invoke({"joined": "\n\n".join(refined_chunks)})

# # ---------- 7) Build Documents for RAG ----------
# # We’ll split the refined text for retrieval. Keep source metadata pointing to the YouTube video id.
rag_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
rag_docs = [
    Document(page_content=chunk, metadata={"source": "youtube", "video_id": "KvUC7bakm-E"})
    for chunk in rag_splitter.split_text(refined_full)
]

# # ---------- 8) Store in Chroma ----------
Chroma.from_documents(
    documents=rag_docs,
    collection_name="htb-fluffy",
    persist_directory="../crawl4ai_store",
    embedding=OllamaEmbeddings(model="nomic-embed-text") 
)

print("✅ Transcript refined and indexed to Chroma.")

# vectorstore = Chroma(
#     collection_name="htb-fluffy", persist_directory="../crawl4ai_store", embedding_function=OllamaEmbeddings(model="nomic-embed-text")
# )

# retriever = vectorstore.as_retriever(k=3)

# question = "From the youtube video transcript, give me plan of how to fully solve the Fluffy challenge in Hack The Box."
# documents = retriever.invoke(question)

# from langchain import hub
# prompt = hub.pull("rlm/rag-prompt")

# rag_chain = prompt | llm | to_text

# # RAG generation
# generation = rag_chain.invoke({"context": documents, "question": question})
# print(generation)