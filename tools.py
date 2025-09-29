from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain.schema import Document
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# LLM
ollama_llm = ChatOllama(model="llama3.1:8b-instruct-q4_0", temperature=0.2, num_ctx=8192)
google_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

# Router
def route_question(state):
    """
    Route question to web search or RAG.

    Args:
        state (dict): The current graph state

    Returns:
        str: Next node to call
    """
    print("---ROUTE QUESTION---")
    prompt = PromptTemplate(
        template="""You are an expert at routing a user question to a vectorstore or web search. \n
        Use the vectorstore for questions on HackTheBox challenges. \n
        You do not need to be stringent with the keywords in the question related to these topics. \n
        Otherwise, use web-search. Give a binary choice 'web_search' or 'vectorstore' based on the question. \n
        Return a JSON with a single key 'datasource' and no premable or explanation. \n
        Question to route: {question}""",
        input_variables=["question"],
    )

    question_router = prompt | ollama_llm | JsonOutputParser()
    question = state["question"]
    source = question_router.invoke({"question": question})
    datasource = source["datasource"]
    if datasource == "vectorstore":
        return "vectorstore"
    elif datasource == "web_search":
        return "web_search"

def decide_to_retrieve(state):
    """
    Determines whether to retrieve documents, or use web search instead when the retrieve count exceeds a threshold.

    Args:
        state (dict): The current graph state
    Returns:
        str: Binary decision for next node to call
    """

    print("---DECIDE TO RETRIEVE OR WEB SEARCH---")
    retrieve_count = state["retrieve_count"]

    if retrieve_count >= 2:
        print("---DECISION: RETRIEVE COUNT EXCEEDED, USE WEB SEARCH---")
        return "max_retrieval_exceeded"
    else:
        print("---DECISION: RETRIEVE---")
        return "max_retrieval_not_exceeded"

# Docs retriever
def retrieve(state):
    """
    Retrieve documents

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, documents, that contains retrieved documents
    """
    print("---RETRIEVE---")
    challenge_name = state["challenge_name"]
    while not challenge_name or not challenge_name.startswith("htb"):
        print("---GUESS CHALLENGE NAME FROM QUESTION---")
        prompt = PromptTemplate(
            template="""You are an expert at extracting the HackTheBox challenge name from a user question. \n
            The challenge name MUST be in the format 'htb-challengename'. \n
            If the question does not reference a HackTheBox challenge, return 'unknown'. \n
            Here is the user question: {question} \n
            Return ONLY the challenge name with NO preamble or explanation.""",
            input_variables=["question"],
        )
        challenge_name_extractor = prompt | ollama_llm | StrOutputParser()
        question = state["question"]
        challenge_name = challenge_name_extractor.invoke({"question": question}).lower().strip()
        if challenge_name == "unknown":
            print("---DECISION: CHALLENGE NAME UNKNOWN, USE WEB SEARCH---")
            return {"documents": None, "question": question, "challenge_name": challenge_name}
        print(f"---CHALLENGE NAME: {challenge_name}---")

    # load the vectorstore
    vectorstore = Chroma(
        collection_name="htb_2025", persist_directory="D:/AI-LLM/Agents/RAGAgent/crawl4ai_store", embedding_function=OllamaEmbeddings(model="nomic-embed-text")
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 8, "filter": {"challenge_name": challenge_name}})
    documents = retriever.invoke(question)

    return {"documents": documents, "question": question, "challenge_name": challenge_name, "retrieve_count": state["retrieve_count"] + 1}

def generate(state):
    """
    Generate answer

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    print("---GENERATE---")

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

    question = state["question"]
    documents = state["documents"]

    # RAG generation
    generation = rag_chain.invoke({"context": documents, "question": question})
    return {"documents": documents, "question": question, "generation": generation, "challenge_name": state["challenge_name"], "generate_count": state["generate_count"] + 1}

def grade_documents(state):
    """
    Determines whether the retrieved documents are relevant to the question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with only filtered relevant documents
    """

    print("---CHECK DOCUMENT RELEVANCE TO QUESTION---")
    prompt = PromptTemplate(
        template="""You are a grader assessing relevance of a retrieved document to a user question. \n 
        Here is the retrieved document: \n\n {document} \n\n
        Here is the user question: {question} \n
        If the document contains keywords related to the user question, grade it as relevant. \n
        It does not need to be a stringent test. The goal is to filter out erroneous retrievals. \n
        Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question. \n
        Provide the binary score as a JSON with a single key 'score' and no premable or explanation.""",
        input_variables=["question", "document"],
    )

    retrieval_grader = prompt | ollama_llm | JsonOutputParser()

    question = state["question"]
    documents = state["documents"]

    if not documents:
        print("---NO DOCUMENTS RETRIEVED, SKIP GRADE---")
        return {"documents": None, "question": question}

    # Score each doc
    filtered_docs = []
    for d in documents:
        score = retrieval_grader.invoke(
            {"question": question, "document": d.page_content}
        )
        grade = score["score"]
        if grade == "yes":
            print("---GRADE: DOCUMENT RELEVANT---")
            filtered_docs.append(d)
        else:
            print("---GRADE: DOCUMENT NOT RELEVANT---")
            continue
    return {"documents": filtered_docs, "question": question, "challenge_name": state["challenge_name"], "retrieve_count": state["retrieve_count"]}

def decide_to_generate(state):
    """
    Determines whether to generate an answer, or re-generate a question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Binary decision for next node to call
    """

    print("---ASSESS GRADED DOCUMENTS---")
    state["question"]
    filtered_documents = state["documents"]

    if not filtered_documents:
        # All documents have been filtered check_relevance
        # We will re-generate a new query
        print(
            "---DECISION: ALL DOCUMENTS ARE NOT RELEVANT TO QUESTION, TRANSFORM QUERY---"
        )
        return "not_relevant"
    else:
        # We have relevant documents, so generate answer
        print("---DECISION: GENERATE---")
        return "relevant"

def grade_generation_v_documents_and_question(state):
    """
    Determines whether the generation is grounded in the document and answers question.

    Args:
        state (dict): The current graph state

    Returns:
        str: Decision for next node to call
    """

    print("---CHECK HALLUCINATIONS---")
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

# Question rewriter
def transform_query(state):
    """
    Transform the query to produce a better question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates question key with a re-phrased question
    """

    print("---TRANSFORM QUERY---")

    re_write_prompt = PromptTemplate(
        template="""You are a question re-writer that converts an input question to a better version that is optimized \n 
        for vectorstore retrieval. Look at the initial and formulate an improved question. \n
        Here is the initial question: \n\n {question}. Improved question with no preamble: \n """,
        input_variables=["generation", "question"],
    )

    question_rewriter = re_write_prompt | ollama_llm | StrOutputParser()

    question = state["question"]
    documents = state["documents"]

    # Re-write question
    better_question = question_rewriter.invoke({"question": question})
    return {"documents": documents, "question": better_question, "challenge_name": state["challenge_name"], "retrieve_count": state["retrieve_count"]}

def web_search(state):
    """
    Web search based on the re-phrased question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with appended web results
    """

    print("---WEB SEARCH---")
    question = state["question"]

    # Web search
    docs = TavilySearchResults(k=3).invoke({"query": question})
    web_results = "\n".join([d["content"] for d in docs])
    web_results = Document(page_content=web_results)

    return {"documents": web_results, "question": question, "challenge_name": state["challenge_name"], "retrieve_count": state["retrieve_count"]}