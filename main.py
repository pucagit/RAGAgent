import pprint
from typing import List
from typing_extensions import TypedDict
from langgraph.graph import START, END, StateGraph
from tools import decide_to_generate, generate, grade_documents, grade_generation_v_documents_and_question, route_question, transform_query, web_search, retrieve
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

workflow = StateGraph(GraphState)

# Define nodes
workflow.add_node("web_search", web_search)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)
workflow.add_node("transform_query", transform_query)

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
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges(
    "grade_documents", 
    decide_to_generate,
    {
        "transform_query": "transform_query",
        "generate": "generate"
    }
)
workflow.add_edge("transform_query", "retrieve")
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
    print = pprint.pp
    inputs: GraphState = {"question": "Give me a full step-by-step of how to solve the Fluffy challenge in HackTheBox.",
                          "generation": "",
                          "documents": []}
    # Run the workflow and get the final state
    for output in app.stream(inputs):
        final_state = next(iter(output.values()))
    # Access the final generation result
    print(final_state["generation"] if final_state["generation"] else "No generation produced.")
