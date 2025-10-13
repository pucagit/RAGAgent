import pprint
from typing import List
from typing_extensions import TypedDict
from langgraph.graph import START, END, StateGraph
from utils.tools import generate, grade_generation_v_documents_and_question, route_question, web_search, retrieve
from dotenv import load_dotenv

load_dotenv()

class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: question
        generation: LLM generation
        documents: list of documents
    """

    question: str
    generation: str
    documents: List[str]
    challenge_name: str
    generate_count: int

workflow = StateGraph(GraphState)

# Define nodes
workflow.add_node("web_search", web_search)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)

# Build graph
workflow.add_conditional_edges(
    START, 
    route_question, 
    {
        "web_search": "web_search",
        "vectorstore": "retrieve"
    }
)
workflow.add_edge("web_search", "generate")
workflow.add_edge("retrieve", "generate")
workflow.add_conditional_edges(
    "generate",
    grade_generation_v_documents_and_question,
    {
        "not_supported": "generate",
        "useful": END,
        "not_useful": "web_search"
    }
)

app = workflow.compile()

# Example usage
if __name__ == "__main__":
    # question = "Give me a full step-by-step of how to solve the TwoMillion challenge in HackTheBox."  # needs web search
    # question = "Give me a full step-by-step on how to solve the Fluffy challenge in HackTheBox." # can be answered with retrieval
    question = "I have done the recon part, show me how to escalate to admin in the Fluffy challenge in HackTheBox."
    print = pprint.pp
    inputs: GraphState = {"question": question,
                          "challenge_name": "",
                          "generation": "",
                          "documents": [],
                          "generate_count": 0}
    # Run the workflow and get the final state
    for output in app.stream(inputs):
        final_state = next(iter(output.values()))

    # Access the final generation result
    # with open(f"rag_response/{final_state['challenge_name']}.md", "w", encoding="utf-8") as f:
    #     f.write(final_state["generation"] if final_state["generation"] else "No generation produced.")
    print(final_state["generation"] if final_state["generation"] else "No generation produced.")
