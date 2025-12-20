from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from llm.client import get_llm

def build_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        MessagesPlaceholder("history"),
        ("human", "{input}"),
    ])
    llm = get_llm()
    return prompt | llm
