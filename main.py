#!/usr/bin/env python3
# coding=utf-8

import asyncio
import csv
import logging
from signal import SIGINT, SIGTERM
import sys
from time import sleep

from aiohttp import ClientConnectionError, ServerDisconnectedError
from nio import (
    AsyncClient,
    AsyncClientConfig,
    InviteMemberEvent,
    LocalProtocolError,
    LoginError,
    RoomMemberEvent,
    RoomMessageText,
)

from bot_actions import add_announcement, Announcement, periodic_sync, sync_data
from callbacks import Callbacks
from config import Config
from storage import Storage

logger = logging.getLogger(__name__)


async def shutdown(loop, client, config, signal=None):
    if getattr(config, "stopping", False):
        return
    config.stopping = True
    logger.info("Shutting down for %s", signal.name if signal else "command")
    await client.close()
    config.sync_task.cancel()
    await sync_data(config)
    loop.stop()
    logger.info("Goodbye")


async def main():
    # Read config file

    # A different config file path can be specified as the first command line argument
    if len(sys.argv) > 1:
        config_filepath = sys.argv[1]
    else:
        config_filepath = "data/config.yaml"
    config = Config(config_filepath)

    # Configure the database
    store = Storage(config.database_filepath)

    # Configuration options for the AsyncClient
    client_config = AsyncClientConfig(
        max_limit_exceeded=0,
        max_timeouts=0,
        store_sync_tokens=True,
        encryption_enabled=True,
    )

    # Initialize the matrix client
    client = AsyncClient(
        config.homeserver_url,
        config.user_id,
        device_id=config.device_id,
        store_path=config.store_filepath,
        config=client_config,
    )

    # Signal handlers
    loop = asyncio.get_event_loop()
    for sig in (SIGINT, SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda sig=sig: asyncio.create_task(shutdown(loop, client, config, sig)),
        )

    # Set up event callbacks
    callbacks = Callbacks(client, store, config)
    client.add_event_callback(callbacks.message, (RoomMessageText,))
    client.add_event_callback(callbacks.invite, (InviteMemberEvent,))
    client.add_event_callback(callbacks.welcome, (RoomMemberEvent,))
    client.add_event_callback(callbacks.message_hopenet, (RoomMessageText,))

    # Periodic token save
    config.sync_task = asyncio.create_task(periodic_sync(config))

    # Schedule announcements
    try:
        with open(config.announcement_csv, "r") as f:
            reader = csv.reader(f)
            for record in reader:
                await add_announcement(
                    config,
                    Announcement(client, record[0], record[1], record[2]),
                    write=False,
                )
    except FileNotFoundError:
        logger.error("No announcements csv")

    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        logger.debug("Starting client")
        try:
            # Try to login with the configured username/password
            try:
                login_response = await client.login(
                    password=config.user_password, device_name=config.device_name,
                )

                # Check if login failed
                if type(login_response) == LoginError:
                    logger.error("Failed to login: %s", login_response.message)
                    return False
            except LocalProtocolError as e:
                # There's an edge case here where the user hasn't installed the correct C
                # dependencies. In that case, a LocalProtocolError is raised on login.
                logger.fatal(
                    "Failed to login. Have you installed the correct dependencies? "
                    "https://github.com/poljar/matrix-nio#installation "
                    "Error: %s",
                    e,
                )
                return False

            # Login succeeded!

            # Sync encryption keys with the server
            # Required for participating in encrypted rooms
            if client.should_upload_keys:
                await client.keys_upload()

            logger.info(f"Logged in as {config.user_id}")
            await client.sync_forever(timeout=30000, full_state=True)

        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")

            # Sleep so we don't bombard the server with login requests
            sleep(15)
        finally:
            # Make sure to close the client connection on disconnect
            await client.close()


asyncio.get_event_loop().run_until_complete(main())
