from db.migrations import run_schema
from auth.flow import login_flow, register_flow
from db.sessions import create_session, list_sessions
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
        choice = input("> ").strip()

        if choice == "1":
            return create_session(user_id), False

        if choice == "2":
            sessions = list_sessions(user_id)
            if not sessions:
                print("No sessions found.\n")
                continue
            
            print("\nYour sessions:")
            for i, (sid, created_at, last_active, _preview) in enumerate(sessions, start=1):
                print(f"{i}) {sid}  (created {created_at}, last {last_active})")

            pick = input("> ").strip()
            if pick.isdigit():
                idx = int(pick) - 1
                if 0 <= idx < len(sessions):
                    return sessions[idx][0], True

            print("Invalid choice.\n")
            continue

        print("Choose 1 or 2.\n")

def main():
    run_schema()
    user_id = menu_auth()

    while True:
        session_id, show_last = menu_sessions(user_id)
        run_chat(session_id, show_last=show_last)

if __name__ == "__main__":
    main()
