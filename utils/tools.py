from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain.prompts import PromptTemplate, ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain.schema import Document
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

load_dotenv()

# LLM
ollama_llm = ChatOllama(model="llama3.1:8b-instruct-q4_0", temperature=0, num_ctx=8192)
google_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

# Router
def route_question(state):
    """
    Route question to web search or RAG.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """
    logging.info("---ROUTE QUESTION---")
    system_prompt = """You are an expert at routing a user question to a vectorstore or web search. \n
    Use the vectorstore for questions on HackTheBox challenges. \n
    You do not need to be stringent with the keywords in the question related to these topics. \n
    Otherwise, use web-search. Give a binary choice 'web_search' or 'vectorstore' based on the question. \n
    Return a JSON with a single key 'datasource' and no premable or explanation. \n"""
    human_prompt = "Route this question to the appropriate datasource: {question}"
    
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template(human_prompt),
        ]
    )

    question_router = prompt | ollama_llm | JsonOutputParser()
    source = question_router.invoke({"question": state["question"]})
    datasource = source["datasource"]
    if datasource == "vectorstore":
        return "vectorstore"
    elif datasource == "web_search":
        return "web_search"

# Docs retriever
def retrieve(state):
    """
    Retrieve documents

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, documents, that contains retrieved documents
    """
    
    question = state["question"]
    challenge_name = state["challenge_name"]
    while not challenge_name:
        logging.info("---GUESS CHALLENGE NAME FROM QUESTION---")
        system_prompt = """You are an expert at extracting the HackTheBox challenge name from a user question.\n
        The challenge name MUST be in the format 'challengename'.\n
        If the question does not reference a HackTheBox challenge, return 'unknown'.\n
        Return ONLY the challenge name with NO preamble or explanation.\n"""
        human_prompt = "Extract the HackTheBox challenge name, from this question: {question}"
        
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(system_prompt),
                HumanMessagePromptTemplate.from_template(human_prompt),
            ]
        )

        challenge_name_extractor = prompt | ollama_llm | StrOutputParser()
        challenge_name = challenge_name_extractor.invoke({"question": question}).lower().strip()
        if challenge_name == "unknown":
            logging.info("---DECISION: CHALLENGE NAME UNKNOWN, USE WEB SEARCH---")
            return {"documents": None, "question": question, "challenge_name": challenge_name}
        logging.info(f"---CHALLENGE NAME: {challenge_name}---")

    logging.info("---RETRIEVE---")
    # load the vectorstore
    vectorstore = Chroma(
        collection_name="htb_2025", 
        persist_directory="D:/AI-LLM/Agents/RAGAgent/crawled_data_store", 
        embedding_function=OllamaEmbeddings(model="bge-m3")
    )

    # retriever = vectorstore.as_retriever(search_kwargs={"k": 8, "filter": {"challenge_name": challenge_name}})
    # documents = retriever.invoke(question)

    # documents = vectorstore.similarity_search(
    #     query=question,
    #     k=10,
    #     filter={"challenge_name": challenge_name},
    # )

    # documents = vectorstore.similarity_search_with_relevance_scores(
    #     query=question,
    #     k=10
    # )
    documents = vectorstore.as_retriever(
        search_kwargs={
            "k": 8, 
            "filter":{
                "basename": f"{challenge_name}.md"
            }
        }
    ).invoke(question)

    return {"documents": documents, "question": question, "challenge_name": challenge_name}

def generate(state):
    """
    Generate answer

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    logging.info("---GENERATE---")
    system_prompt = """You are an expert at question-answering tasks.\n
        Use the following pieces of retrieved context to answer the question.\n
        If you don't know the answer, just say that you don't know.\n
        Provide a conversational answer with a step-by-step guide on how to solve the challenge.\n"""
    human_prompt = "Here is the context: {context}\nAnswer this question base on the above context: {question}"
    
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template(human_prompt),
        ]
    )

    # rag_chain = prompt | google_llm | StrOutputParser()
    rag_chain = prompt | ollama_llm | StrOutputParser()

    question = state["question"]
    documents = state["documents"]

    # RAG generation
    generation = rag_chain.invoke({"context": documents, "question": question})
    return {"documents": documents, "question": question, "generation": generation, "challenge_name": state["challenge_name"], "generate_count": state["generate_count"] + 1}


def grade_generation_v_documents_and_question(state):
    """
    Determines whether the generation is grounded in the document and answers question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Decision for next node to call
    """

    logging.info("---CHECK HALLUCINATIONS---")
    # Hallucination grader
    prompt = PromptTemplate(
        template="""You are a grader assessing whether an answer is grounded in / supported by a set of facts. \n 
        Here are the facts:
        \n ------- \n
        {documents} 
        \n ------- \n
        Here is the answer: {generation}
        Give a binary score 'yes' or 'no' score to indicate whether the answer is grounded in / supported by a set of facts. \n
        Provide the binary score as a JSON with a single key 'score' and no preamble or explanation.""",
        input_variables=["generation", "documents"],
    )

    hallucination_grader = prompt | ollama_llm | JsonOutputParser()

    # Answer grader
    prompt = PromptTemplate(
        template="""You are a grader assessing whether an answer is useful to resolve a question. \n 
        Here is the answer:
        \n ------- \n
        {generation} 
        \n ------- \n
        Here is the question: {question}
        Give a binary score 'yes' or 'no' to indicate whether the answer is useful to resolve a question. \n
        Provide the binary score as a JSON with a single key 'score' and no preamble or explanation.""",
        input_variables=["generation", "question"],
    )

    answer_grader = prompt | ollama_llm | JsonOutputParser()

    question = state["question"]
    documents = state["documents"]
    generation = state["generation"]

    score = hallucination_grader.invoke(
        {"documents": documents, "generation": generation}
    )
    hallucination_grade = score["score"]

    # Check hallucination
    if hallucination_grade == "yes":
        print("---DECISION: GENERATION IS GROUNDED IN DOCUMENTS---")
        # Check answer relevance to question
        print("---GRADE GENERATION vs QUESTION---")
        score = answer_grader.invoke({"question": question, "generation": generation})
        answer_grade = score["score"]
        if answer_grade == "yes":
            print("---DECISION: GENERATION ADDRESSES QUESTION---")
            return "useful"
        else:
            print("---DECISION: GENERATION DOES NOT ADDRESS QUESTION---")
            return "not_useful"
    else:
        generate_count = state["generate_count"]
        if generate_count < 3:
            print("---DECISION: GENERATION IS NOT GROUNDED IN DOCUMENTS, RE-TRY---")
            return "not_supported"
        else:
            print("---DECISION: MAX GENERATION ATTEMPTS EXCEEDED, SKIPPING RE-TRY---")
            return "useful"

def web_search(state):
    """
    Web search based on the re-phrased question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with appended web results
    """

    logging.info("---WEB SEARCH---")
    question = state["question"]

    # Web search
    docs = TavilySearchResults(k=3).invoke({"query": question})
    web_results = "\n".join([d["content"] for d in docs])
    web_results = Document(page_content=web_results)

    return {"documents": web_results, "question": question, "challenge_name": state["challenge_name"]}