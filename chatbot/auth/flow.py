from getpass import getpass
from db.users import create_user, auth_user, user_exists

def register_flow() -> str | None:
    print("\n---- Register ----")
    name = input("Name: ").strip()
    nickname = input("Nickname: ").strip()
    password = getpass("Password: ").strip()
    age_str = input("Age: ").strip()
    
    if not name or not nickname or not password or not age_str.isdigit():
        print("Invalid input.\n")
        return None
    
    if user_exists(nickname):
        print("Nickname already taken.\n")
        return None

    create_user(name=name, nickname=nickname, password=password, age=int(age_str))
    print("User created. Now you can login.\n")
    return None

def login_flow() -> str | None:
    print("\n---- Login ----")
    nickname = input("Nickname: ").strip()
    password = getpass("Password: ").strip()
    
    user_id = auth_user(nickname, password)
    if not user_id:
        print("Invalid nickname or password.\n")
        return None
    
    print("Logged in.\n")
    return(user_id)
