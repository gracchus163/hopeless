# coding=utf-8

from asyncio import create_task
from datetime import datetime, timedelta
import logging

from nio import JoinError

from bot_actions import check_hopenet, warn_if_hopenet
from bot_commands import Command
from message_responses import Message

logger = logging.getLogger(__name__)


class Callbacks(object):
    def __init__(self, client, store, config):
        """
        Args:
            client (nio.AsyncClient): nio client used to interact with matrix

            store (Storage): Bot storage

            config (Config): Bot configuration parameters
        """
        self.client = client
        self.store = store
        self.config = config
        self.command_prefix = config.command_prefix

    async def message(self, room, event):
        """Callback for when a message event is received

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageText): The event defining the message

        """
        # Extract the message text
        msg = event.body

        # Ignore messages from ourselves
        if event.sender == self.client.user:
            return

        logger.debug(
            f"Bot message received for room {room.display_name} | "
            f"{room.user_name(event.sender)}: {msg}"
        )

        # Process as message if in a public room without command prefix
        has_command_prefix = msg.startswith(self.command_prefix)
        if not has_command_prefix and not room.is_group:
            # General message listener
            message = Message(self.client, self.store, self.config, msg, room, event)
            await message.process()
            return

        # Otherwise if this is in a 1-1 with the bot or features a command prefix,
        # treat it as a command
        if has_command_prefix:
            # Remove the command prefix
            msg = msg[len(self.command_prefix) :]

        command = Command(self.client, self.store, self.config, msg, room, event)
        # Spawn a task and don't wait for it
        create_task(command.process())

    async def invite(self, room, event):
        """Callback for when an invite is received. Join the room specified in the invite"""
        logger.debug(f"Got invite to {room.room_id} from {event.sender}.")

        # Attempt to join 3 times before giving up
        for attempt in range(3):
            result = await self.client.join(room.room_id)
            if type(result) == JoinError:
                logger.error(
                    f"Error joining room {room.room_id} (attempt %d): %s",
                    attempt,
                    result.message,
                )
            else:
                break
        else:
            logger.error("Unable to join room: %s", room.room_id)

        # Successfully joined room
        logger.info(f"Joined {room.room_id}")

    async def welcome(self, room, event):
        """Callback for when a user joins a room

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageText): The event defining the message

        """

        # Ignore our own joins and non-join events
        if event.sender == self.client.user or event.membership != "join":
            return

        logger.debug("Join received for %s: %s", room.display_name, event.sender)

        async with self.config._hopenet_warn_lock:
            self.config.hopenet_warn_times[event.sender] = datetime.now()
        create_task(check_hopenet(self.client, self.config, room, event, event.sender))

    async def message_hopenet(self, room, event):
        """Callback for !check and notifying users of legacy host on message

        Args:
            room (nio.rooms.MatrixRoom): The room the event came from

            event (nio.events.room_events.RoomMessageText): The event defining the message

        """
        # Ignore messages from ourselves
        if event.sender == self.client.user:
            return

        logger.debug(
            "Message received in %s from %s: %s",
            room.display_name,
            event.sender,
            event.body,
        )

        # Process as message if in a public room without command prefix
        if event.body.lower().split(maxsplit=1)[0] == "!check":
            args = event.body.split()
            if len(args) > 1:
                user = args[1]
            else:
                user = event.sender
            create_task(warn_if_hopenet(self.client, self.config, room, event, user))
            return

        async with self.config._hopenet_warn_lock:
            do_check = False
            if self.config.hopenet_warn_interval > 0 and (
                event.sender not in self.config.hopenet_warn_times
                or self.config.hopenet_warn_times[event.sender]
                < (
                    datetime.now()
                    - timedelta(minutes=self.config.hopenet_warn_interval)
                )
            ):
                self.config.hopenet_warn_times[event.sender] = datetime.now()
                do_check = True
        if do_check:  # Outside lock
            create_task(
                check_hopenet(
                    self.client, self.config, room, event, event.sender, only_fail=True
                )
            )
