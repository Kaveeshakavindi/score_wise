import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

def get_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=8192,
        streaming=True,
    )

def get_text_content(message) -> str:
    """Extract plain text from a message's content.

    Anthropic responses represent content as a list of content blocks
    (e.g. [{"type": "text", "text": "..."}]) rather than a plain string.
    """
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content) if content else ""
