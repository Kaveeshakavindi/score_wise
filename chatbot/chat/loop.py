import sys
from chat.chain import build_prompt, get_llm_with_tools
from llm.client import get_text_content
from chat.rag import retrieve, set_active_session
from chat.tools import get_tools
from chat.title import generate_session_title
from db.messages import load_history, save_message, load_last_exchange
from db.sessions import touch_session, set_session_title
from langchain_core.messages import HumanMessage, ToolMessage

def run_chat(session_id: str, user_context: str, show_last: bool = False) -> None:
    prompt = build_prompt(user_context)
    llm = get_llm_with_tools()
    tool_map = {tool.name: tool for tool in get_tools()}

    print("\nChat started. Press Ctrl+C to stop.\n")
    if show_last:
        last_user, last_assistant = load_last_exchange(session_id)
        if last_user:
            print(f"Last you: {last_user}")
        if last_assistant:
            print(f"Last bot: {last_assistant}")
        if last_user or last_assistant:
            print("")

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            set_active_session(session_id)
            history = load_history(session_id)
            is_first_turn = len(history) == 0
            context_text = _build_context(user_input)

            messages = prompt.format_messages(history=history, input=user_input, context=context_text)
            response = llm.invoke(messages)
            while getattr(response, "tool_calls", None):
                messages.append(response)
                tool_messages, tool_used_index = _run_tool_calls(response.tool_calls, tool_map)
                messages.extend(tool_messages)
                if tool_used_index:
                    context_text = _build_context(user_input)
                    if context_text:
                        # Anthropic only allows system messages at the very start of a
                        # conversation, so mid-loop context is injected as a labeled
                        # human-turn block instead of a SystemMessage.
                        messages.append(HumanMessage(
                            content=f"<system-reminder>Relevant context (if any):\n{context_text}</system-reminder>"
                        ))
                response = llm.invoke(messages)

            response_text = get_text_content(response).strip()
            _print_in_chunks(response_text)

            save_message(session_id, "user", user_input)
            save_message(session_id, "assistant", response_text)
            if is_first_turn:
                title = generate_session_title(user_input, response_text)
                set_session_title(session_id, title)
            touch_session(session_id)
    except KeyboardInterrupt:
        print("\nSession saved. Returning to menu\n")

def _run_tool_calls(tool_calls, tool_map):
    results = []
    used_index = False
    for call in tool_calls:
        tool = tool_map.get(call.get("name"))
        if not tool:
            output = f"Error: unknown tool '{call.get('name')}'"
        else:
            try:
                output = tool.invoke(call.get("args", {}))
                if tool.name in {"read_file", "read_url"}:
                    used_index = True
            except Exception as exc:
                output = f"Error: tool execution failed: {exc}"
        results.append(ToolMessage(content=str(output), tool_call_id=call.get("id")))
    return results, used_index

def _build_context(query: str) -> str:
    try:
        chunks = retrieve(query, k=4)
    except Exception:
        return ""
    return "\n\n".join(chunks)

def _print_in_chunks(text: str, chunk_size: int = 24) -> None:
    print("Bot: ", end="")
    sys.stdout.flush()
    for i in range(0, len(text), chunk_size):
        print(text[i:i + chunk_size], end="")
        sys.stdout.flush()
    print("\n")
