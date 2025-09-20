import asyncio
import requests 
from xml.etree import ElementTree
from typing import List, Tuple
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode # type: ignore

async def crawl_parallel(urls: List[str]) -> List[Tuple[str, str]]:
    """
    Returns a list of (url, markdown_text) tuples.
    """
    crawl_result: List[Tuple[str, str]] = []
    run_conf = CrawlerRunConfig(cache_mode=CacheMode.BYPASS).clone(stream=False)

    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, config=run_conf)
        for res in results:
            if res.success:
                md = res.markdown.raw_markdown or ""
                print(f"[OK] {res.url}, length: {len(md)}")
                crawl_result.append((res.url, md))
            else:
                print(f"[ERROR] {res.url} => {res.error_message}")

    return crawl_result

def get_crawl4ai_docs_urls() -> List[str]:
    """
    Fetches all URLs from the Crawl4AI documentation.
    Uses the sitemap (https://docs.crawl4ai.com/sitemap.xml) to get these URLs.

    Returns:
        List[str]: List of URLs
    """
    sitemap_url = "https://docs.crawl4ai.com/sitemap.xml"
    try:
        response = requests.get(sitemap_url)
        response.raise_for_status()
        
        # Parse the XML
        root = ElementTree.fromstring(response.content)
        
        # Extract all URLs from the sitemap
        # The namespace is usually defined in the root element
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls: List[str] = [t for loc in root.findall('.//ns:loc', namespace) if (t := loc.text) is not None]
        
        return urls
    except Exception as e:
        print(f"Error fetching sitemap: {e}")
        return []        

async def build_chunks_from_crawl(
    urls: List[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):
    # 1) Crawl pages
    crawl_results = await crawl_parallel(urls)  # -> List[(url, markdown)]

    # 2) Wrap into LangChain Documents (keep provenance in metadata!)
    docs: List[Document] = [
        Document(
            page_content=markdown_text,
            metadata={
                "source": url,        # for RAG citations
                "format": "markdown", # helpful hint
            },
        )
        for (url, markdown_text) in crawl_results if markdown_text.strip()
    ]

    # 3) Split into chunks (token-aware)
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    doc_splits: List[Document] = text_splitter.split_documents(docs)

    return doc_splits

async def main():
    urls = get_crawl4ai_docs_urls()
    if urls:
        print(f"Found {len(urls)} URLs to crawl")
        doc_splits = await build_chunks_from_crawl(urls)
        Chroma.from_documents(
            documents=doc_splits, 
            collection_name="crawl4ai-docs", 
            persist_directory="./chroma_store", 
            embedding=OllamaEmbeddings(model="nomic-embed-text")
        )
    else:
        print("No URLs found to crawl")    

if __name__ == "__main__":
    asyncio.run(main())