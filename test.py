
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate


# LLM
ollama_llm = ChatOllama(model="llama3.1:8b-instruct-q4_0", temperature=0.2, num_ctx=8192)


challenge_name = ""
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
    question = "I am stuck on the media challenge in HackTheBox. Can you help me solve it?"
    challenge_name = challenge_name_extractor.invoke({"question": question}).lower().strip()
    if challenge_name == "unknown":
        print("---DECISION: CHALLENGE NAME UNKNOWN, USE WEB SEARCH---")
    print(f"---CHALLENGE NAME: {challenge_name}---")