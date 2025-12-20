from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from llm.client import get_llm

def build_chain(user_context: str):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. User info: {user_context}. Answer in short. Do not use special characters."),
        MessagesPlaceholder("history"),
        ("human", "{input}"),
    ])
    llm = get_llm()
    return prompt.partial(user_context=user_context) | llm
