from nio import Api
from hashlib import sha256
def valid_token(token, tokens,sender):
    h = sha256()
    h.update(token.encode("utf-8"))
    msg = h.hexdigest()
    if msg in tokens:
        if tokens[msg] == 'unused':
            return True, msg
        elif tokens[msg] == sender:
            return True, msg
    return False, ""

async def community_invite(client, group, sender):#
    if not group:
        return
    path = "groups/{}/admin/users/invite/{}".format(group,sender)
    data = {"user_id":sender}
    query_parameters = {"access_token": client.access_token}
    path = Api._build_path(path, query_parameters)
    print(path)
    await client.send("PUT",
            path,
            Api.to_json(data),
            headers = {"Content-Type": "application/json"}
            )
    return

def is_admin(user):
    user = str(user)
    print(user)
    try:
        f = open("admin.csv", "rt")
        for nick in f.readlines():
            print(nick)
            if user == nick.rstrip():
                f.close()
                return True
        f.close()
    except FileNotFoundError:
        print("no admin.csv")
    return False

def get_alias(roomid):
    return roomid
