# coding=utf-8

from datetime import datetime
import logging
import re

from dateutil import tz

from bot_actions import (
    add_announcement,
    Announcement,
    community_invite,
    get_roomid,
    is_admin,
    is_authed,
    sync_data,
    valid_token,
)
from chat_functions import send_text_to_room

logger = logging.getLogger(__name__)


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
        logger.debug("Got command from %s: %r", self.event.sender, self.command)
        trigger = self.command.lower()
        if trigger.startswith("help"):
            await self._show_help()
        elif trigger.startswith("request"):
            await self._process_request("attendee")
        elif trigger.startswith("ticket"):
            await self._process_request("attendee")
        elif trigger.startswith("volunteer"):
            await self._volunteer_request("volunteer")
            # await self._process_request("volunteer")
        elif trigger.startswith("presenter"):
            await self._process_request("presenter")
        elif trigger.startswith("hack"):
            await self._the_planet()
        elif trigger.startswith("trashing"):
            await self._trashing()
        elif trigger.startswith("notice"):
            if is_admin(self.config, self.event.sender):
                await self._notice()
        elif trigger.startswith("sync"):
            if is_admin(self.config, self.event.sender):
                await self._sync()
        elif trigger.startswith("invite_group"):
            if is_admin(self.config, self.event.sender):
                await self._invite_group()
        elif trigger.startswith("invite"):
            if is_admin(self.config, self.event.sender):
                await self._invite()
        elif trigger.startswith("oncall"):
            await self._volunteer_request("oncall")
        elif trigger.startswith("schedule_announce"):
            if is_admin(self.config, self.event.sender):
                await self._schedule_announcement()
        elif re.search(r"\bty\b|\bthx\b|thank|\bthanx\b", trigger) is not None:
            await send_text_to_room(
                self.client, self.room.room_id, "Hey no problem, have a good HOPE!"
            )
        elif re.search(r"\bhi\b|\bhello\b|\bhey\b", trigger) is not None:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                "Hi there, I'm a bot. Try typing `help` if you need some guidance",
            )
        elif len(trigger) >= 63 and " " not in trigger:
            response = (
                "I think you posted just your ticket code. Add the ticket "
                "code from your email after the command, like this:  \n"
                "`ticket a1b2c3d4e5...`  \n"
                "or  \n"
                "`presenter a1b2c3d4e5...`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)

    async def _process_request(self, ticket_type):
        """!h $ticket_type $token"""
        if not self.args:
            response = (
                "Add the ticket code from your email after the command, like this:  \n"
                f"`{self.command} a1b2c3d4e5...`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        logger.debug("ticket cmd from %s for %s", self.event.sender, ticket_type)
        token = str(self.args[0])
        if len(token) != 64:
            response = (
                "Token must be 64 characters, check your ticket again or if you "
                "have trouble, please send an email to helpdesk2020@helpdesk.hope.net"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        lock = self.config._attendee_token_lock
        tokens = self.config.tokens
        rooms = self.config.rooms
        group = self.config.community
        if ticket_type == "presenter":
            lock = self.config._presenter_token_lock
            tokens = self.config.presenter_tokens
            rooms = self.config.presenter_rooms + self.config.rooms
            group = self.config.presenter_community
        elif ticket_type == "volunteer":
            lock = self.config._volunteer_token_lock
            tokens = self.config.volunteer_tokens
            rooms = self.config.volunteer_rooms
            group = self.config.volunteer_community

        # Make sure other tasks don't interfere with our token[] manipulation or writing
        async with lock:
            valid, h = valid_token(token, tokens, self.event.sender)
            if valid:
                response = (
                    "Verified ticket. You should now be invited to the HOPE "
                    f"{ticket_type} chat rooms and community."
                )
                await send_text_to_room(self.client, self.room.room_id, response)
                logger.debug("Inviting %s to %s", self.event.sender, ",".join(rooms))
                for r in rooms:
                    await self.client.room_invite(r, self.event.sender)
                await community_invite(self.client, group, self.event.sender)

                if tokens[h] == "unused":
                    tokens[h] = self.event.sender
                return
            else:
                logger.info(
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

    async def _volunteer_request(self, req_type):
        if len(self.args) != 1:
            return
        if self.args[0] != self.config.volunteer_pass:
            response = "Sorry, wrong password, try again?"
            # response = (
            #     "What are you, stoned or stupid? You don't hack a "
            #     "bank across state lines from your house, you'll get nailed "
            #     "by the FBI. Where are your brains, in your ass? Don't you "
            #     "know anything?"
            # )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        if req_type == "oncall":
            response = "Inviting you to the HOPE oncall rooms"
            await send_text_to_room(self.client, self.room.room_id, response)
            await self.client.room_invite(self.config.oncall_room, self.event.sender)
        else:
            response = "Inviting you to the HOPE volunteer rooms..."
            await send_text_to_room(self.client, self.room.room_id, response)
            for r in self.config.volunteer_rooms:
                await self.client.room_invite(r, self.event.sender)
            await send_text_to_room(
                self.client,
                self.room.room_id,
                "Inviting you to the volunteer community",
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
        logger.warning(
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
        ret, room_id = await get_roomid(self.client, self.args[0])
        if not ret:
            response = "Could not find a roomid for that room name"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        await send_text_to_room(self.client, room_id, msg, notice=False)
        await send_text_to_room(self.client, self.room.room_id, "Sent")

    async def _sync(self):
        logger.warning("sync used by %s", self.event.sender)
        await sync_data(self.config)
        await send_text_to_room(self.client, self.room.room_id, "Sunk")

    async def _invite(self):
        # manually invite user to a room
        if len(self.args) != 2:
            response = (
                "Add the full username then the full room name after invite:  \n"
                "`invite @user:server.net #room:server.net`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        ret, room_id = await get_roomid(self.client, self.args[1])
        if not ret:
            response = "Could not find a roomid for that room name"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        await self.client.room_invite(room_id, self.args[0])

    async def _invite_group(self):
        # manually invite user to a room
        if len(self.args) != 2:
            response = (
                "Add the full username then the group name after invite_group:  \n"
                "`invite_group @user:server.net [attendee|volunteer|presenter]`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        if self.args[1] == "attendee":
            rooms = self.config.rooms
        elif self.args[1] == "volunteer":
            rooms = self.config.volunteer_rooms
        elif self.args[1] == "presenter":
            rooms = self.config.presenter_rooms
        else:
            response = "not a valid group. attendee, volunteer or presenter"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        for r in rooms:
            await self.client.room_invite(r, self.args[0])
        response = "invited to {} group".format(self.args[1])
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _join(self):
        # user can join (be invited to) rooms they are authorised for
        if len(self.args) != 1:
            response = (
                "Add the fully qualified roomname after join like this:  \n"
                "`join #oncall:hope.net`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        ret, r = await get_roomid(self.client, self.args[0])
        if not ret:
            response = "Could not find a roomid for that room name"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        if await is_authed(self.client, self.config, self.event.sender, r):
            print("TODO")

    async def _schedule_announcement(self):
        """Add a scheduled announcement
        This does NOT automatically tag @room
        """
        if len(self.args) < 3:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                (
                    "Usage:  \n"
                    f"`{self.command} 2020-07-30T15:30:00 #room-name:hope.net "
                    "@room\\n# Hello!\\nThis is a test.`  \n"
                    "Dates and times must be LOCALTIME. "
                    "You must use `@room` in the message if you want it. "
                    "Double check your message, only the bot admin can fix errors!"
                ),
            )
            return

        parts = self.command.split(maxsplit=3)[1:]
        # Time
        try:
            time = datetime.fromisoformat(parts[0])
        except ValueError as e:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                f"Error: `{e}`  \n"
                "Time should be localtime and formatted like 2020-07-30T15:30",
            )
            return
        time = time.replace(tzinfo=tz.gettz("America/New_York"))
        future = time - datetime.now(tz.UTC)
        if future.total_seconds() < 10:
            await send_text_to_room(
                self.client, self.room.room_id, "Time must be in the future"
            )
            return
        # Room
        room = parts[1]
        ret, room_id = await get_roomid(self.client, room)
        if not ret:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                "Could not find a roomid for that room name",
            )
            return
        # Message
        message = parts[2]

        logger.info(
            "Announcement scheduled for %s at %s by %s: %r",
            room,
            time,
            self.event.sender,
            message,
        )

        await add_announcement(
            self.config, Announcement(self.client, time, room, message)
        )
        await send_text_to_room(
            self.client,
            self.room.room_id,
            "Scheduled for {}d{}h{}m from now".format(
                future.days, future.seconds // (60 * 60), (future.seconds // 60) % 60
            ),
        )
