import asyncio, argparse
from sitemap_parser import get_urls_from_sitemap
from typing import List, Tuple
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode # type: ignore
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def crawl_parallel(urls: List[str]) -> List[Tuple[str, str]]:
    """
    Returns a list of (url, markdown_text) tuples.
    """
    crawl_result: List[Tuple[str, str]] = []

    md_generator = DefaultMarkdownGenerator(
        options={"ignore_links": True, "escape_html": False, "body_width": 80}
    )

    run_conf = CrawlerRunConfig(
        markdown_generator=md_generator, 
        cache_mode=CacheMode.BYPASS, 
        excluded_tags = ["a"]
    ).clone(stream=False)

    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, config=run_conf)
        for res in results: # type: ignore
            if res.success:
                md = res.markdown.raw_markdown or ""
                print(f"[OK] {res.url}, length: {len(md)}")
                # print(md)
                crawl_result.append((res.url, md))
            else:
                print(f"[ERROR] {res.url} => {res.error_message}")

    return crawl_result

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
    parser = argparse.ArgumentParser(description="Crawl URLs from a sitemap and store in Chroma DB.")
    parser.add_argument("sitemap_url", help="URL of the sitemap or sitemap index")
    parser.add_argument("-p", "--pattern", default="", help="Regex pattern to filter URLs")
    parser.add_argument("--max_depth", type=int, default=3, help="Max recursion depth for sitemap indexes")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds")

    args = parser.parse_args()
    urls = get_urls_from_sitemap(args.sitemap_url, args.pattern, args.max_depth, args.timeout)
    # for url in urls:
    #     print(url)
    print(f"Found {len(urls)} URLs from sitemap")
    await crawl_parallel(urls)
    if urls:
        print(f"Found {len(urls)} URLs to crawl")
        doc_splits = await build_chunks_from_crawl(urls)
        Chroma.from_documents(
            documents=doc_splits, 
            collection_name="crawl4ai-docs", 
            persist_directory="./crawl4ai_store", 
            embedding=OllamaEmbeddings(model="nomic-embed-text")
        )
    else:
        print("No URLs found to crawl")    

if __name__ == "__main__":
    asyncio.run(main())