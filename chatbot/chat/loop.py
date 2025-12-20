import sys
from chat.chain import build_chain
from db.messages import load_history, save_message, load_last_exchange
from db.sessions import touch_session

def run_chat(session_id: str, show_last: bool = False) -> None:
    chain = build_chain()
    
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
            
            history = load_history(session_id)
            
            stream = chain.stream({
                "input": user_input,
                "history": history,
            })
            
            print("Bot: ", end="")
            sys.stdout.flush()
            response_parts = []
            for chunk in stream:
                text = getattr(chunk, "content", "")
                if text:
                    response_parts.append(text)
                    print(text, end="")
                    sys.stdout.flush()
            response_text = "".join(response_parts).strip()
            print("\n")
            
            save_message(session_id, "user", user_input)
            save_message(session_id, "assistant", response_text)
            touch_session(session_id)
    except KeyboardInterrupt:
        print("\nSession saved. Returning to menu\n")
