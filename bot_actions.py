# coding=utf-8

import asyncio
import csv
from datetime import datetime
from hashlib import sha256
import logging
from os import fsync, rename
from typing import Optional

from dateutil import tz
from nio import Api, RoomResolveAliasResponse

from chat_functions import send_text_to_room

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
    logger.debug("community_invite path: %r", path)
    await client.send(
        "PUT", path, Api.to_json(data), headers={"Content-Type": "application/json"}
    )
    return


def is_admin(config, user):
    user = str(user)
    logger.debug("is_admin? %s", user)
    try:
        with open(config.admin_csv_path, "r") as f:
            for nick in f.readlines():
                if user == nick.rstrip():
                    logger.debug("is_admin! %s", user)
                    return True
    except FileNotFoundError:
        logger.error("No admin csv")
    logger.debug("not admin: %s", user)
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
        await asyncio.sleep(config.sync_interval)
        await sync_data(config)


async def get_roomid(client, alias):
    resp = await client.room_resolve_alias(alias)
    if not isinstance(resp, RoomResolveAliasResponse):
        logger.info("notice: bad room alias %s", alias)
        return False, ""
    return True, resp.room_id


class Announcement:
    time: datetime
    room: str
    message: str
    _task: Optional[asyncio.Task]
    _logger: logging.Logger

    def __init__(self, client, time: datetime, room: str, message: str):
        self._client = client
        if not isinstance(time, datetime):
            self.time = datetime.fromisoformat(time)
        else:
            self.time = time
        self.room = room
        self.message = message
        self._task = None
        self._logger = logging.getLogger(__name__)

    def to_list(self) -> list:
        return [self.time.isoformat(), self.room, self.message]

    async def schedule(self):
        if self.time > datetime.now(tz.UTC) and (
            self._task is None or self._task.cancelled()
        ):
            self._task = asyncio.create_task(self._announce_later())
        else:
            logger.debug("Not scheduling past announcement for %s", self.time)

    async def _announce_later(self):
        """Coroutine to wait until scheduled time for announcement"""
        wait_seconds = (self.time - datetime.now(tz.UTC)).total_seconds()
        self._logger.info(
            "Waiting %s seconds to announce to %s at %s: %r",
            wait_seconds,
            self.room,
            self.time,
            self.message,
        )
        await asyncio.sleep(wait_seconds)
        await self.announce()

    async def announce(self):
        """Post announcement"""
        self._logger.info(
            "Announcing to %s at %s: %r", self.room, self.time, self.message,
        )
        ret, room_id = await get_roomid(self._client, self.room)
        if not ret:
            self._logger.error(
                "Could not find a roomid for scheduled message to %s", self.room
            )
            return
        await send_text_to_room(self._client, room_id, self.message)


async def add_announcement(config, new_announcement, write=True):
    logger.debug("Adding announcement")
    async with config._announcement_lock:
        if new_announcement.time.tzinfo is None:
            raise Exception("MissingTimezone")
        await new_announcement.schedule()
        config._announcements.append(new_announcement)
    if write:
        await write_announcements(config)


async def reset_announcements(config, stop=False):
    logger.info("Resetting announcements")
    async with config._announcement_lock:
        if stop:
            # Stop all
            tasks = [
                t
                for t in asyncio.all_tasks()
                if t.get_coro().__name__ == "_announce_at"
            ]
            [task.cancel() for task in tasks]
            await asyncio.gather(tasks)

        # Start all
        [a.schedule() for a in config._announcements]
    logger.debug("Reset announcements")


async def write_announcements(config):
    logger.info("Writing announcement csv")
    async with config._announcement_lock:
        filename = config.announcement_csv
        filename_temp = filename + ".atomic"
        with open(filename_temp, "w") as f:
            csv_writer = csv.writer(f)
            for announcement in config._announcements:
                csv_writer.writerow(announcement.to_list())
            f.flush()
            fsync(f.fileno())
        rename(filename_temp, filename)
    logger.debug("Wrote announcement csv")


async def is_authed(client, config, sender, roomid):
    #   GET /groups/<group_id>/users
    #    path = "groups/{}/rooms".format("+hopeless:hope.net")
    #    query_parameters = {"access_token": client.access_token}
    #    path = Api._build_path(path, query_parameters)
    #    resp = await client._send("GET", path )
    #    print(resp)
    if sender in config.volunteer_tokens.values():
        logger.info("authed for volunteers")
        await client.room_invite(roomid, sender)
    return False
