from chat_functions import send_text_to_room
from bot_actions import valid_token, community_invite

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
        if self.command.startswith("help"):
            await self._show_help()
        elif self.command.startswith("request"):
            await self._process_request("attendee")
        elif self.command.startswith("ticket"):
            await self._process_request("attendee")
        elif self.command.startswith("volunteer"):
            await self._volunteer_request()
            #await self._process_request("volunteer")
        elif self.command.startswith("presenter"):
            await self._process_request("presenter")
        elif self.command.startswith("hack"):
            await self._the_planet()
        elif self.command.startswith("trashing"):
            await self._trashing()

    async def _process_request(self, group):
        """!h $group $token"""
        if not self.args: 
            response = "You need to add your token after {}".format(self.command)
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        print("args are:" + " ".join([str(x) for x in self.args]))
        print("from: " + self.event.sender)
        token = str(self.args[0])
        if len(token) != 64:
            response = "Token must be 64 characters, check your ticket again or contact aestetix or valka"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        tokens = self.config.tokens
        rooms = self.config.rooms
        group = self.config.community
        filename = "tokens.csv"
        if group == "presenter":
            tokens = self.config.presenter_tokens
            rooms = self.config.presenter_rooms
            group = self.config.presenter_community
            filename = "presenters.csv"
        elif group == "volunteer":
            tokens = self.config.volunteer_tokens
            rooms = self.config.volunteer_rooms
            group = self.config.volunteer_community
            filename = "volunteers.csv"

        valid, h = valid_token(token, tokens,self.event.sender)
        if valid:
            response = "Verified, congrats. You should now be invited to the {} rooms".format(group)
            await send_text_to_room(self.client, self.room.room_id, response)
            print(rooms)
            await send_text_to_room(self.client, self.room.room_id, "inviting you to the HOPE community")
            await community_invite(self.client, group, self.event.sender)
            for r in rooms:
                await self.client.room_invite(r, self.event.sender)
            if tokens[h] == "unused":
                tokens[h] = self.event.sender
                with open(filename, 'w') as f:
                    for key in tokens.keys():
                        f.write("%s,%s\n"%(key,tokens[key]))
            return
        else:
            response = "This is not a valid token, check your ticket again or contact aestetix or valka"
            await send_text_to_room(self.client, self.room.room_id, response)
            return

    async def _volunteer_request(self):
        response = "Inviting you to the HOPE volunteer rooms"
        await send_text_to_room(self.client, self.room.room_id, response)
        for r in self.config.volunteer_rooms:
            await self.client.room_invite(r, self.event.sender)
        await send_text_to_room(self.client, self.room.room_id, "inviting you to the HOPE community")
        await community_invite(self.client, self.config.volunteer_community, self.event.sender)
        return

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = ("Hello, I am a bot made with matrix-nio! To get invited to the official conference channels message me with ticket $mytoken")
            await send_text_to_room(self.client, self.room.room_id, text)
            return
    async def _the_planet(self):
        text = "HACK THE PLANET https://youtu.be/YV78vobCyIo?t=55"
        await send_text_to_room(self.client, self.room.room_id, text)
        return

    async def _trashing(self):
        text = """They\'re TRASHING our rights, man! They\'re
	TRASHING the flow of data! They\'re TRASHING!
	TRASHING! TRASHING! HACK THE PLANET! HACK
	THE PLANET!"""
        await send_text_to_room(self.client, self.room.room_id, text)
        return
    async def _group(self):
        await send_text_to_room(self.client, self.room.room_id, "inviting to group")
        await community_invite(self.client, self.config, self.event.sender)
