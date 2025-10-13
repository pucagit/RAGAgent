import asyncio, argparse, re
from sitemap_parser import get_urls_from_sitemap
from urllib.parse import urlparse, unquote
from typing import List, Tuple
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode  # type: ignore
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# ==== Simple helper ====
def extract_challenge_slug(url: str) -> str:
    """https://0xdf.gitlab.io/2025/09/26/htb-babytwo.html -> htb-babytwo"""
    if not url:
        return ""
    p = urlparse(url)
    path = unquote(p.path or "").rstrip("/")
    if not path:
        return ""
    last = path.split("/")[-1]
    slug = re.sub(r"\.(html?|md|markdown|php|aspx?)$", "", last, flags=re.I)
    return slug

# ==== Crawler ====
async def crawl_parallel(urls: List[str]) -> List[Tuple[str, str]]:
    """Returns a list of (url, markdown_text) tuples."""
    crawl_result: List[Tuple[str, str]] = []

    md_generator = DefaultMarkdownGenerator(
        options={"ignore_links": True, "escape_html": False, "body_width": 80}
    )
    run_conf = CrawlerRunConfig(
        markdown_generator=md_generator,
        cache_mode=CacheMode.BYPASS,
        excluded_tags=["a"]
    ).clone(stream=False)

    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, config=run_conf)
        for res in results:  # type: ignore
            if res.success:
                md = res.markdown.raw_markdown or ""
                print(f"[OK] {res.url}, length: {len(md)}")
                crawl_result.append((res.url, md))
            else:
                print(f"[ERROR] {res.url} => {res.error_message}")

    return crawl_result

# ==== Build chunks with metadata (url, challenge_name) ====
async def build_chunks_from_crawl(
    urls: List[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    crawl_results = await crawl_parallel(urls)  

    docs: List[Document] = []
    for url, markdown_text in crawl_results:
        if not markdown_text.strip():
            continue
        docs.append(
            Document(
                page_content=markdown_text,
                metadata={
                    "url": url,                              
                    "challenge_name": extract_challenge_slug(url),  
                },
            )
        )

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return text_splitter.split_documents(docs)

async def main():
    parser = argparse.ArgumentParser(description="Crawl URLs from a sitemap and store in Chroma DB.")
    parser.add_argument("sitemap_url", help="URL of the sitemap or sitemap index")
    parser.add_argument("-p", "--pattern", default="", help="Regex pattern to filter URLs")
    parser.add_argument("--max_depth", type=int, default=3, help="Max recursion depth for sitemap indexes")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds")
    args = parser.parse_args()

    urls = get_urls_from_sitemap(args.sitemap_url, args.pattern, args.max_depth, args.timeout)
    print(f"Found {len(urls)} URLs from sitemap")

    if not urls:
        print("No URLs found to crawl")
        return

    print(f"Found {len(urls)} URLs to crawl")
    doc_splits = await build_chunks_from_crawl(urls)

    Chroma.from_documents(
        documents=doc_splits,
        collection_name="htb_2025",                
        persist_directory="D:/AI-LLM/Agents/RAGAgent/crawled_data_store",  
        embedding=OllamaEmbeddings(model="bge-m3")
    )
    print(f"Persisted {len(doc_splits)} chunks -> collection 'htb_2025' in 'crawled_data_store'")

if __name__ == "__main__":
    asyncio.run(main())
