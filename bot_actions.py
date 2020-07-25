# coding=utf-8

from hashlib import sha256
import logging

from nio import Api

logger = logging.getLogger(__name__)


def valid_token(token, tokens, sender):
    h = sha256()
    h.update(token.encode("utf-8"))
    msg = h.hexdigest()
    if msg in tokens:
        if tokens[msg] == "unused":
            return True, msg
        elif tokens[msg] == sender:
            return True, msg
    return False, msg


async def community_invite(client, group, sender):  #
    if not group:
        return
    path = "groups/{}/admin/users/invite/{}".format(group, sender)
    data = {"user_id": sender}
    query_parameters = {"access_token": client.access_token}
    path = Api._build_path(path, query_parameters)
    logging.debug("community_invite path: %r", path)
    await client.send(
        "PUT", path, Api.to_json(data), headers={"Content-Type": "application/json"}
    )
    return


def is_admin(config, user):
    user = str(user)
    logging.debug("is_admin? %s", user)
    try:
        with open(config.admin_csv_path, "r") as f:
            for nick in f.readlines():
                logging.debug("is_admin line: %s", nick)
                if user == nick.rstrip():
                    f.close()
                    return True
    except FileNotFoundError:
        logging.error("No admin csv")
    return False


def get_alias(roomid):
    return roomid
