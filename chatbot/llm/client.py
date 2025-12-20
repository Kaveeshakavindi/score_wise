import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ["LMSTUDIO_MODEL"],
        base_url=os.environ["LMSTUDIO_BASE_URL"],
        api_key="lm_studio",
        temperature=0.7,
        streaming=True,
    )
