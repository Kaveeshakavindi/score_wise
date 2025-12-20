from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from chat.tools import get_tools
from llm.client import get_llm

def build_prompt(user_context: str):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. User info: {user_context}. Use tools when helpful. If a file path is provided, use read_file to load it. If a URL is provided, use read_url to load it. Answer based on the retrieved content."),
        ("system", "Relevant context (if any):\n{context}"),
        MessagesPlaceholder("history"),
        ("human", "{input}"),
    ])
    return prompt.partial(user_context=user_context)

def get_llm_with_tools():
    llm = get_llm()
    return llm.bind_tools(get_tools())
