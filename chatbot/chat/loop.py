import sys
from chat.chain import build_chain
from chat.title import generate_session_title
from db.messages import load_history, save_message, load_last_exchange
from db.sessions import touch_session, set_session_title

def run_chat(session_id: str, user_context: str, show_last: bool = False) -> None:
    chain = build_chain(user_context)

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
            is_first_turn = len(history) == 0

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
            if is_first_turn:
                title = generate_session_title(user_input, response_text)
                set_session_title(session_id, title)
            touch_session(session_id)
    except KeyboardInterrupt:
        print("\nSession saved. Returning to menu\n")
