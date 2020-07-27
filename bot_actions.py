# coding=utf-8

from asyncio import sleep
import csv
from hashlib import sha256
import logging
from os import fsync, rename

from nio import Api, RoomResolveAliasResponse

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


async def community_invite(client, group, sender):
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


async def write_csv(config, ticket_type):
    logger.info("Writing %s ticket csv", ticket_type)

    lock = config._attendee_token_lock
    tokens = config.tokens
    filename = config.tokens_path
    if ticket_type == "presenter":
        lock = config._presenter_token_lock
        tokens = config.presenter_tokens
        filename = config.presenter_tokens_path
    elif ticket_type == "volunteer":
        lock = config._volunteer_token_lock
        tokens = config.volunteer_tokens
        filename = config.volunteer_tokens_path

    async with lock:
        filename_temp = filename + ".atomic"
        with open(filename_temp, "w") as f:
            csv_writer = csv.writer(f)
            csv_writer.writerows(tokens.items())
            f.flush()
            fsync(f.fileno())
        rename(filename_temp, filename)

    logger.debug("Done writing")


async def sync_data(config):
    for ticket_type in ["attendee", "volunteer", "presenter"]:
        await write_csv(config, ticket_type)


async def periodic_sync(config):
    while True:
        await sleep(config.sync_interval)
        await sync_data(config)


async def get_roomid(client, alias):
    resp = await client.room_resolve_alias(alias)
    print(resp)
    if not isinstance(resp, RoomResolveAliasResponse):
        logging.info("notice: bad room alias %s", alias)
        return False, ""
    return True, resp.room_id


async def is_authed(client, config, sender, roomid):
    #   GET /groups/<group_id>/users
    #    path = "groups/{}/rooms".format("+hopeless:hope.net")
    #    query_parameters = {"access_token": client.access_token}
    #    path = Api._build_path(path, query_parameters)
    #    resp = await client._send("GET", path )
    #    print(resp)
    if sender in config.volunteer_tokens.values():
        print("authed for volunteers")
        await client.room_invite(roomid, sender)
    return False
