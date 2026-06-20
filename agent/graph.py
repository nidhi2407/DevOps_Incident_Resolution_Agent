from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from agent.state import AgentState
from agent.prompts import RCA_PROMPT
from dotenv import load_dotenv
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
vectordb = Chroma(persist_directory="data/chroma_db", embedding_function=embeddings)
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)


def retrieve_node(state: AgentState) -> AgentState:
    docs = vectordb.similarity_search(state["alert"], k=3)
    state["context"] = [d.page_content for d in docs]
    return state


def analyze_node(state: AgentState) -> AgentState:
    context_text = "\n\n".join(state["context"])
    chain = RCA_PROMPT | llm
    response = chain.invoke({"context": context_text, "alert": state["alert"]})
    text = response.content

    state["rca"] = text

    if "CONFIDENCE: High" in text:
        state["confidence"] = "High"
    elif "CONFIDENCE: Medium" in text:
        state["confidence"] = "Medium"
    else:
        state["confidence"] = "Low"

    return state


def should_retry(state: AgentState) -> str:
    if state["confidence"] == "Low" and state["retry_count"] < 2:
        return "retry"
    return "done"


def retry_node(state: AgentState) -> AgentState:
    state["retry_count"] += 1
    docs = vectordb.similarity_search(state["alert"], k=5)
    state["context"] = [d.page_content for d in docs]
    return state


workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("retry", retry_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "analyze")
workflow.add_conditional_edges("analyze", should_retry, {
    "retry": "retry",
    "done": END
})
workflow.add_edge("retry", "analyze")

agent_graph = workflow.compile()