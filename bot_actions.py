from nio import Api
from hashlib import sha256
def valid_token(token, tokens):
    h = sha256()
    h.update(token.encode("utf-8"))
    msg = h.hexdigest()
    print(msg)
    if msg in tokens:
        return tokens[msg] == 'unused'
    return False

async def community_invite(client, config, sender):#"+test-community:hope.net"
    #path = "https://matrix.hope.net/_matrix/client/r0/groups/+test-community:hope.net/{}/users/invite".format(sender)
    path = "groups/+test-community:hope.net/{}/users/invite".format(sender)
    data = {"user_id":sender}
    query_parameters = {"requester_user_id": client.user}
    #msg = ( "POST", client.homeserver + Api._build_path(path, query_parameters), Api.to_json(data))
    #path = "https://<host>/_matrix/client/r0/groups/%2B<group_localpart>%3A<server_name>/admin/users/invite/"
    #client.send(method, path, data)headers:optional, trace_context:any, timeout:optional
    print(path)
    path = client.homeserver + Api._build_path(path, query_parameters)
    print(path)
    print(data)
    print(Api.to_json(data))
    print(str(Api.to_json(data)))
    await client.client_session.request("POST", path, Api.to_json(data))
    return True
