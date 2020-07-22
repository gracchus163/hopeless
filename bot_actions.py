from nio import Api
from hashlib import sha256
def valid_token(token, tokens,sender):
    h = sha256()
    h.update(token.encode("utf-8"))
    msg = h.hexdigest()
    print(msg)
    if msg in tokens:
        if tokens[msg] == 'unused':
            return True, msg
        elif tokens[msg] == sender:
            return True, msg
    return False, ""

async def community_invite(client, config, sender):#
    if not config.community:
        return
    path = "groups/{}/admin/users/invite/{}".format(config.community,sender)
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
