# coding=utf-8

from asyncio import Lock
import csv
import logging
from os import fsync, rename

from bot_actions import community_invite, is_admin, valid_token
from chat_functions import send_text_to_room
from nio import RoomResolveAliasResponse

logger = logging.getLogger(__name__)

_attendee_token_lock = Lock()
_presenter_token_lock = Lock()
_volunteer_token_lock = Lock()


class Command(object):
    def __init__(self, client, store, config, command, room, event):
        """A command made by a user

        Args:
            client (nio.AsyncClient): The client to communicate to matrix with

            store (Storage): Bot storage

            config (Config): Bot configuration parameters

            command (str): The command and arguments

            room (nio.rooms.MatrixRoom): The room the command was sent in

            event (nio.events.room_events.RoomMessageText): The event describing the command
        """
        self.client = client
        self.store = store
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]

    async def process(self):
        """Process the command"""
        logging.debug("Got command from %s: %r", self.event.sender, self.command)
        trigger = self.command.lower()
        if trigger.startswith("help"):
            await self._show_help()
        elif trigger.startswith("request"):
            await self._process_request("attendee")
        elif trigger.startswith("ticket"):
            await self._process_request("attendee")
        elif trigger.startswith("volunteer"):
            # await self._volunteer_request()
            await self._process_request("volunteer")
        elif trigger.startswith("presenter"):
            await self._process_request("presenter")
        elif trigger.startswith("hack"):
            await self._the_planet()
        elif trigger.startswith("trashing"):
            await self._trashing()
        elif trigger.startswith("notice"):
            if is_admin(self.event.sender):
                await self._notice()

    async def _process_request(self, ticket_type):
        """!h $ticket_type $token"""
        if not self.args:
            response = (
                "Add the ticket code from your email after the command, like this:  \n"
                f"`{self.command} a1b2c3d4e5...`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        logging.debug("ticket cmd from %s for %s", self.event.sender, ticket_type)
        token = str(self.args[0])
        if len(token) != 64:
            response = (
                "Token must be 64 characters, check your ticket again or if you "
                "have trouble, please send an email to helpdesk2020@helpdesk.hope.net"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        lock = _attendee_token_lock
        tokens = self.config.tokens
        rooms = self.config.rooms
        group = self.config.community
        filename = "tokens.csv"
        if ticket_type == "presenter":
            lock = _presenter_token_lock
            tokens = self.config.presenter_tokens
            rooms = self.config.presenter_rooms
            group = self.config.presenter_community
            filename = "presenters.csv"
        elif ticket_type == "volunteer":
            lock = _volunteer_token_lock
            tokens = self.config.volunteer_tokens
            rooms = self.config.volunteer_rooms
            group = self.config.volunteer_community
            filename = "volunteers.csv"

        # Make sure other tasks don't interfere with our token[] manipulation or writing
        async with lock:
            valid, h = valid_token(token, tokens, self.event.sender)
            if valid:
                response = (
                    "Verified ticket. You should now be invited to the HOPE "
                    f"{ticket_type} chat rooms."
                )
                if tokens[h] == "unused" and not self.config.repeat_community_invite:
                    # Unused token, can't resend? Warn.
                    response += (
                        "  \nBe sure to accept the community invite, "
                        "we can only send it once!"
                    )
                await send_text_to_room(self.client, self.room.room_id, response)

                logging.debug("Inviting %s to %s", self.event.sender, ",".join(rooms))
                for r in rooms:
                    await self.client.room_invite(r, self.event.sender)

                if tokens[h] == "unused" or self.config.repeat_community_invite:
                    await community_invite(self.client, group, self.event.sender)

                if tokens[h] == "unused":
                    tokens[h] = self.event.sender
                    filename_temp = filename + ".atomic"
                    with open(filename_temp, "w") as f:
                        csv_writer = csv.writer(f)
                        csv_writer.writerows(tokens.items())
                        f.flush()
                        fsync(f.fileno())
                    rename(filename_temp, filename)

                return
            else:
                logging.info(
                    "ticket invalid: %s: %s %s (%s)",
                    self.event.sender,
                    ticket_type,
                    token,
                    tokens.get(h, "<invalid>"),
                )
                # notify outside lock block
        response = (
            "This is not a valid token, check your ticket again or "
            "email helpdesk2020@helpdesk.hope.net  \n"
            "If you are a `volunteer` or `presenter`, use those commands "
            "instead of `ticket`"
        )
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _volunteer_request(self):
        response = "Inviting you to the HOPE volunteer rooms..."
        await send_text_to_room(self.client, self.room.room_id, response)
        for r in self.config.volunteer_rooms:
            await self.client.room_invite(r, self.event.sender)
        await send_text_to_room(
            self.client, self.room.room_id, "Inviting you to the HOPE community"
        )
        await community_invite(
            self.client, self.config.volunteer_community, self.event.sender
        )

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = (
                "Hello, I'm the HOPE CoreBot! To be invited to the official "
                "conference channels message me with `ticket <your-token-here>`. "
                "You can find more information (important for presenters) on the "
                "[conference bot wiki](https://wiki.hope.net/index.php?title=Conference_bot)."
            )
            await send_text_to_room(self.client, self.room.room_id, text)

    async def _the_planet(self):
        text = "HACK THE PLANET https://youtu.be/YV78vobCyIo?t=55"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _trashing(self):
        text = """They\'re TRASHING our rights, man! They\'re
        TRASHING the flow of data! They\'re TRASHING!
        TRASHING! TRASHING! HACK THE PLANET! HACK
        THE PLANET!"""
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _group(self):
        await send_text_to_room(self.client, self.room.room_id, "inviting to group")
        await community_invite(self.client, self.config, self.event.sender)

    async def _notice(self):
        msg = "@room\n" + self.command.split(maxsplit=2)[2]
        logging.warning(
            "notice used by %s at %s to send: %r",
            self.event.sender,
            self.room.room_id,
            msg,
        )
        if len(self.args) < 2:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                "notice args: <room-alias\\> <strings\\>,,,",
            )
            return
        resp = await self.client.room_resolve_alias(self.args[0])
        if not isinstance(resp, RoomResolveAliasResponse):
            logging.info("notice: bad room alias %s", self.args[0])
            await send_text_to_room(
                self.client, self.room.room_id, "Invalid room alias"
            )
            return
        room_id = resp.room_id
        await send_text_to_room(self.client, room_id, msg)
        await send_text_to_room(self.client, self.room.room_id, "Sent")

    async def _invite(self):
        # invite user to set of rooms
        pass
