from typing import List
from typing_extensions import TypedDict
from utils.tools import retrieve
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# Create an MCP server
mcp = FastMCP(
    name="RAG Test Server",
    host="0.0.0.0",
    port=6666
)

class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: question
        documents: list of documents
    """

    question: str
    documents: List[str]
    challenge_name: str

@mcp.tool()
def retrieve_only_handler(question: str, challenge_name: str) -> List[str]:
    """Runs the retrieve node and returns the found documents
    Args:
        question (str): The input question
        challenge_name (str): The name of the challenge in lowercase, e.g. "fluffy", "twomillion"
    Returns:
        documents: List[str]
    """
    # Prepare base state
    state: GraphState = {
        "question": question,
        "challenge_name": challenge_name,
        "documents": [],
    }

    resp = retrieve(state)
    return resp["documents"]


# Start the MCP server (this will block unless your FastMCP uses non-blocking run)
if __name__ == "__main__":
    documents = retrieve_only_handler("How to solve the Fluffy challenge in HackTheBox?", "fluffy")
    print(documents)
    # mcp.run(transport="stdio")