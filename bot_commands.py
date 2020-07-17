from chat_functions import send_text_to_room
from bot_actions import valid_email, valid_token

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
        if self.command.startswith("echo"):
            await self._echo()
        elif self.command.startswith("help"):
            await self._show_help()
        elif self.command.startswith("request"):
            await self._process_request()
        else:
            await self._unknown_command()

    async def _process_request(self):
        """!h request $email $token"""
        print("args are:" + " ".join([str(x) for x in self.args]))
        email = str(self.args[0])
        print("email: " + email)
        if not valid_email(email):
            response = "Not a valid email, try again. request arguments are: $email $token"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        token = str(self.args[1])
        if len(token) != 6:
            response = "Token must be 36 characters, check your ticket again or contact valka"
            await send_text_to_room(self.client, self.room.room_id, response)
            return
        if valid_token(token):
            response = "Verified, congrats. You should now be invited to the official rooms"
            await send_text_to_room(self.client, self.room.room_id, response)
   #        invite(user)
            return
        else:
            response = "This is not a valid token, check your ticket again or contact valka"
            await send_text_to_room(self.client, self.room.room_id, response)
            return


    
    async def _echo(self):
        """Echo back the command's arguments"""
        response = " ".join(self.args)
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = ("Hello, I am a bot made with matrix-nio! Use `help commands` to view "
                    "available commands.")
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "rules":
            text = "These are the rules!"
        elif topic == "commands":
            text = "Available commands"
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
