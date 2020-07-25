# coding=utf-8

import logging

from bot_actions import community_invite, is_admin, valid_token, get_roomid, is_authed, sync_data

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
        logging.debug("Got command from %s: %r", self.event.sender, self.command)
        trigger = self.command.lower()
        if trigger.startswith("help"):
            await self._show_help()
        elif trigger.startswith("request"):
            await self._process_request("attendee")
        elif trigger.startswith("ticket"):
            await self._process_request("attendee")
        elif trigger.startswith("volunteer"):
            await self._volunteer_request()
            #await self._process_request("volunteer")
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

        #elif trigger.startswith("join"):
         #   await self._join()


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
        lock = self.config._attendee_token_lock
        tokens = self.config.tokens
        rooms = self.config.rooms
        group = self.config.community
        if ticket_type == "presenter":
            lock = self.config._presenter_token_lock
            tokens = self.config.presenter_tokens
            rooms = self.config.presenter_rooms+self.config.volunteer_rooms
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
        ret, room_id = get_roomid(self.client, self.args[0])
        if not ret:
            response = ("Could not find a roomid for that room name")
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        await send_text_to_room(self.client, room_id, msg)
        await send_text_to_room(self.client, self.room.room_id, "Sent")

    async def _sync(self):
        logging.warning("sync used by %s", self.event.sender)
        await sync_data(self.config)
        await send_text_to_room(self.client, self.room.room_id, "Sunk")

    async def _invite(self):
        # TODO manually invite user to set of rooms
        pass

    async def _join(self):
        # user can be invited to rooms they are authorised for
        if len(self.args) != 1:
            response = (
                "Add the fully qualified roomname after join like this:  \n"
                f"`join #oncall:hope.net`"
            )
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        ret, r = await get_roomid(self.client, self.args[0])
        if not ret:
            response = ("Could not find a roomid for that room name")
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        if await is_authed(self.client, self.config, self.event.sender, r):
            print("TODO")

    async def _volunteer_request(self):
        if len(self.args) != 1:
            return
        if self.args[0] != self.config.volunteer_pass:
            response = ("What are you, stoned or stupid? You don't hack a bank across state lines from your house, you'll get nailed by the FBI. Where are your brains, in your ass? Don't you know anything?")
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        response = "Inviting you to the HOPE volunteer rooms..."
        await send_text_to_room(self.client, self.room.room_id, response)
        for r in self.config.volunteer_rooms:
            await self.client.room_invite(r, self.event.sender)
        await send_text_to_room(
            self.client, self.room.room_id, "Inviting you to the volunteer community"
        )
        await community_invite(
            self.client, self.config.volunteer_community, self.event.sender
        )
        await self.client.room_invite(r, self.event.sender)
