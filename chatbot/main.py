from db.migrations import run_schema
from auth.flow import login_flow, register_flow
from db.sessions import create_session, delete_all_sessions, delete_session, list_sessions
from db.users import get_user_profile
from chat.loop import run_chat

def menu_auth() -> str:
    while True:
        print("1) Login")
        print("2) Register")
        choice = input("> ").strip()

        if choice == "1":
            user_id = login_flow()
            if user_id:
                return user_id
        elif choice == "2":
            register_flow()
        else:
            print("Choose 1 or 2.\n")

def menu_sessions(user_id: str) -> tuple[str, bool]:
    while True:
        print("1) New chat")
        print("2) Resume previous chat")
        print("3) Delete a chat")
        print("4) Delete all chats")
        choice = input("> ").strip()

        if choice == "1":
            return create_session(user_id), False

        if choice == "2":
            sessions = list_sessions(user_id)
            if not sessions:
                print("No sessions found.\n")
                continue

            print("\nYour sessions:")
            for i, (sid, title) in enumerate(sessions, start=1):
                title_text = title or "Untitled chat"
                print(f"{i}) {title_text}  ({sid})")

            pick = input("> ").strip()
            if pick.isdigit():
                idx = int(pick) - 1
                if 0 <= idx < len(sessions):
                    return sessions[idx][0], True

            print("Invalid choice.\n")
            continue

        if choice == "3":
            sessions = list_sessions(user_id)
            if not sessions:
                print("No sessions found.\n")
                continue

            print("\nSelect chat to delete:")
            for i, (sid, title) in enumerate(sessions, start=1):
                title_text = title or "Untitled chat"
                print(f"{i}) {title_text}  ({sid})")

            pick = input("> ").strip()
            if pick.isdigit():
                idx = int(pick) - 1
                if 0 <= idx < len(sessions):
                    confirm = input("Delete this chat? (y/N) ").strip().lower()
                    if confirm == "y":
                        delete_session(sessions[idx][0])
                        print("Chat deleted.\n")
                    else:
                        print("Canceled.\n")
                    continue

            print("Invalid choice.\n")
            continue

        if choice == "4":
            confirm = input("Delete ALL chats? (y/N) ").strip().lower()
            if confirm == "y":
                delete_all_sessions(user_id)
                print("All chats deleted.\n")
            else:
                print("Canceled.\n")
            continue

        print("Choose 1, 2, 3, or 4.\n")

def _format_user_context(user_profile: dict[str, str | int] | None) -> str:
    if not user_profile:
        return "Name: unknown; Nickname: unknown; Age: unknown"
    name = user_profile.get("name", "unknown")
    nickname = user_profile.get("nickname", "unknown")
    age = user_profile.get("age", "unknown")
    return f"Name: {name}; Nickname: {nickname}; Age: {age}"

def main():
    run_schema()
    user_id = menu_auth()
    user_profile = get_user_profile(user_id)
    user_context = _format_user_context(user_profile)

    while True:
        session_id, show_last = menu_sessions(user_id)
        run_chat(session_id, user_context, show_last=show_last)

if __name__ == "__main__":
    main()
