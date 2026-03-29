import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.agents.tools import tool_search_web, tool_web_scrape

async def run_demo():
    print("🦅 GoatRaw v2 — Real-World Task Execution Demo")
    print("---------------------------------------------")
    
    query = "top 5 AI automation agencies in London"
    print(f"🔍 Task: Find {query}...")
    
    # Use the DuckDuckGo fallback in tool_search_web
    results = await tool_search_web(query, num_results=5)
    
    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return

    print(f"✅ Found {len(results['results'])} results via {results['source']}:")
    for i, res in enumerate(results['results'], 1):
        print(f"\n[{i}] {res['title']}")
        print(f"    URL: {res['url']}")
        print(f"    Snippet: {res['snippet'][:150]}...")
        
        # Scrape the first one as a deep dive
        if i == 1:
            print(f"\n📄 Deep Dive: Scraping {res['url']}...")
            scrape = await tool_web_scrape(res['url'])
            if scrape['status'] == 'success':
                content = scrape['content'][:500].replace('\n', ' ')
                print(f"    Content Preview: {content}...")
            else:
                print(f"    ❌ Scrape failed: {scrape.get('error')}")

if __name__ == "__main__":
    asyncio.run(run_demo())
