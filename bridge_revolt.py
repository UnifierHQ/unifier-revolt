"""
Unifier - A sophisticated Discord bot uniting servers and platforms
Copyright (C) 2024  Green, ItsAsheer

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

---------

This program includes subprograms from works that are licensed under the
MIT license. Licenses/copyright notices for those works have been listed
below.

---

Revolt.py
Copyright (c) 2021-present Zomatree

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import nextcord
from nextcord.ext import commands
from revolt.ext import commands as rv_commands
from revolt.ext.commands import Command, Group
import asyncio
import aiohttp
import revolt
import traceback
import time
from utils import log
import random
import string
import os
import emoji as pymoji
import datetime
import re
import json
import sys
from typing import Optional, Union, Any

try:
    import ujson as json  # pylint: disable=import-error
except:
    pass

mentions = nextcord.AllowedMentions(everyone=False, roles=False, users=False)

def timetoint(t):
    try:
        return int(t)
    except:
        pass
    if not type(t) is str:
        t = str(t)
    total = 0
    if t.count('d')>1 or t.count('w')>1 or t.count('h')>1 or t.count('m')>1 or t.count('s')>1:
        raise ValueError('each identifier should never recur')
    t = t.replace('n','n ').replace('d','d ').replace('w','w ').replace('h','h ').replace('m','m ').replace('s','s ')
    times = t.split()
    for part in times:
        if part.endswith('d'):
            multi = int(part[:-1])
            total += (86400 * multi)
        elif part.endswith('w'):
            multi = int(part[:-1])
            total += (604800 * multi)
        elif part.endswith('h'):
            multi = int(part[:-1])
            total += (3600 * multi)
        elif part.endswith('m'):
            multi = int(part[:-1])
            total += (60 * multi)
        elif part.endswith('s'):
            multi = int(part[:-1])
            total += multi
        else:
            raise ValueError('invalid identifier')
    return total

class EmbedField:
    def __init__(self, name, value):
        self.name = name
        self.value = value

class Embed(revolt.SendableEmbed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = []
        self.raw_description = kwargs.get('description', None)
        self.raw_colour = kwargs.get('color', None) or kwargs.get('colour', None)
        self.footer = None

    @property
    def description(self):
        if self.fields:
            toreturn = (
                (self.raw_description + '\n\n') if self.raw_description else ''
            )+ '\n\n'.join([f'**{field.name}**\n{field.value}' for field in self.fields])
        else:
            toreturn = self.raw_description
        if self.footer:
            footer_text = "\n".join([f'##### {line}' for line in self.footer.split('\n')])
            toreturn = f'{toreturn}\n\n{footer_text}'
        return toreturn

    @description.setter
    def description(self, value):
        self.raw_description = value

    @property
    def colour(self):
        if type(self.raw_colour) is int:
            return '#' + hex(self.raw_colour)[2:].zfill(6)

        return self.raw_colour

    @colour.setter
    def colour(self, value):
        self.raw_colour = value

    def add_field(self, name, value):
        self.fields.append(EmbedField(name, value))

    def clear_fields(self):
        self.fields = []

    def insert_field_at(self, index, name, value):
        self.fields.insert(index, EmbedField(name, value))

    def remove_field(self, index):
        self.fields.pop(index)

    def set_field_at(self, index, name, value):
        self.fields[index] = EmbedField(name, value)

    def set_footer(self, text):
        self.footer = text

def is_room_restricted(room,db,compatibility_mode):
    try:
        if compatibility_mode:
            restricted = room in db['restricted']
        else:
            restricted = db['rooms'][room]['meta']['restricted']
        if restricted:
            return True
        else:
            return False
    except:
        traceback.print_exc()
        return False

def is_room_locked(room,db,compatibility_mode):
    try:
        if compatibility_mode:
            locked = room in db['locked']
        else:
            locked = db['rooms'][room]['meta']['locked']
        if locked:
            return True
        else:
            return False
    except:
        traceback.print_exc()
        return False

def genid():
    value = ''
    for i in range(6):
        letter = random.choice(string.ascii_lowercase + string.digits)
        value = '{0}{1}'.format(value, letter)
    return value

class Revolt(commands.Cog,name='Revolt Support'):
    """An extension that enables Unifier to run on Revolt. Manages the Revolt instance, as well as Revolt-to-Revolt and Revolt-to-external bridging.

    Developed by Green"""
    def __init__(self, bot, tokenstore=None):
        self.bot = bot
        if not 'revolt' in self.bot.config.get('external', ['revolt']):
            # revolt is intentionally lowercase
            raise RuntimeError('revolt is not listed as an external service in configuration. More info: https://wiki.unifierhq.org/setup-selfhosted/getting-started/unifier-older-versions#installing-revolt-support')
        if not hasattr(self.bot, 'revolt_client'):
            self.bot.revolt_client = None
            self.bot.revolt_session = None
            self.bot.revolt_client_task = asyncio.create_task(self.revolt_boot())
        self.logger = log.buildlogger(self.bot.package, 'revolt.core', self.bot.loglevel)
        self.__tokenstore = tokenstore

    def db(self):
        return self.bot.db

    class Client(rv_commands.CommandsClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.bot = None
            self.logger = None
            self.compatibility_mode = False

        def dispatch(self, event: str, *args: Any) -> None:
            """Dispatch an event, this is typically used for testing and internals.

            Parameters
            ----------
            event: class:`str`
                The name of the event to dispatch, not including `on_`
            args: :class:`Any`
                The arguments passed to the event
            """

            # This is basically a slightly modified version of Revolt.py's dispatch function,
            # but it will ignore invalid state errors for the sake of keeping the console log
            # clean.

            if temp_listeners := self.temp_listeners.get(event, None):
                for check, future in temp_listeners:
                    if check(*args):
                        try:
                            if len(args) == 1:
                                future.set_result(args[0])
                            else:
                                future.set_result(args)
                        except asyncio.exceptions.InvalidStateError:
                            # return to mimic original behavior, just without the error
                            return

                self.temp_listeners[event] = [(c, f) for c, f in temp_listeners if not f.done()]

            for listener in self.listeners.get(event, []):
                asyncio.create_task(listener(*args))

            if func := getattr(self, f"on_{event}", None):
                asyncio.create_task(func(*args)) # pylint: disable=E1102

        def add_bot(self,bot):
            """Adds a Discord bot to the Revolt client."""
            self.bot = bot

        def add_logger(self,logger):
            self.logger = logger

        async def get_prefix(self, message: revolt.Message):
            return self.bot.command_prefix

        async def on_ready(self):
            self.logger.info('Revolt client booted!')
            if not hasattr(self.bot, 'platforms_former'):
                self.compatibility_mode = True
                return
            if 'revolt' in self.bot.platforms.keys():
                self.bot.platforms['revolt'].attach_bot(self)
            else:
                while not 'revolt' in self.bot.platforms_former.keys():
                    # wait until support plugin has been loaded
                    await asyncio.sleep(1)
                self.bot.platforms.update(
                    {'revolt':self.bot.platforms_former['revolt'].RevoltPlatform(self,self.bot)}
                )

        async def on_raw_reaction_add(self, event):
            try:
                msg = await self.bot.bridge.fetch_message(event['id'])
            except:
                return

            if event['user_id'] in self.bot.db['fullbanned']:
                return

            emoji = event['emoji_id']
            if pymoji.is_emoji(emoji):
                pass
            else:
                emoji = await self.fetch_emoji(event['emoji_id'])
                emoji = f'<r:{emoji.name}:{emoji.id}>'

            await msg.add_reaction(emoji, event['user_id'], platform='revolt')

        async def on_raw_reaction_remove(self, event):
            try:
                msg = await self.bot.bridge.fetch_message(event['id'])
            except:
                return

            if event['user_id'] in self.bot.db['fullbanned']:
                return

            emoji = event['emoji_id']
            if pymoji.is_emoji(emoji):
                pass
            else:
                emoji = await self.fetch_emoji(event['emoji_id'])
                emoji = f'<r:{emoji.name}:{emoji.id}>'

            await msg.remove_reaction(emoji, event['user_id'])

        async def on_message(self, message):
            roomname = None
            if self.compatibility_mode:
                roomkey = 'rooms_revolt'
            else:
                roomkey = 'rooms'
            for key in self.bot.db[roomkey]:
                try:
                    if self.compatibility_mode:
                        if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
                            roomname = key
                            break
                    else:
                        if message.channel.id in str(self.bot.db['rooms'][key]['revolt'][message.server.id]):
                            roomname = key
                            break
                except:
                    pass
            if message.author.id==self.user.id:
                return
            t = time.time()
            if message.author.id in f'{self.bot.db["banned"]}':
                if t >= self.bot.db["banned"][message.author.id]:
                    self.bot.db["banned"].pop(message.author.id)
                    self.bot.db.save_data()
                else:
                    return

            is_dm = False
            try:
                if message.server.id in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][message.server.id]:
                        self.bot.db["banned"].pop(message.server.id)
                        self.bot.db.save_data()
                    else:
                        return
            except LookupError:
                is_dm = True
            if message.content==f'{self.bot.command_prefix}agree':
                return
            elif message.content.startswith(self.bot.command_prefix) and not message.author.bot:
                return await self.process_commands(message)
            if not roomname or is_dm:
                return

            try:
                pr_roomname = self.bot.config['posts_room']
            except:
                pr_roomname = self.bot.db['rooms'][list(self.bot.db['rooms'].keys())[self.bot.config['pr_room_index']]]
            try:
                pr_ref_roomname = self.bot.config['posts_ref_room']
            except:
                pr_ref_roomname = self.bot.db['rooms'][
                    list(self.bot.db['rooms'].keys())[self.bot.config['pr_ref_room_index']]]

            is_pr = roomname == pr_roomname and (
                self.bot.config['allow_prs'] if 'allow_prs' in list(self.bot.config.keys()) else False or
                self.bot.config['allow_posts'] if 'allow_posts' in list(self.bot.config.keys()) else False
            )
            is_pr_ref = roomname == pr_ref_roomname and (
                self.bot.config['allow_prs'] if 'allow_prs' in list(self.bot.config.keys()) else False or
                self.bot.config['allow_posts'] if 'allow_posts' in list(self.bot.config.keys()) else False
            )

            should_delete = False
            emojified = False

            if '[emoji:' in message.content or is_pr or is_pr_ref:
                emojified = True
                should_delete = True

            if not message.server.get_member(self.user.id).get_channel_permissions(message.channel).manage_messages:
                if emojified or is_pr_ref:
                    return await message.channel.send(
                        'Parent message could not be deleted. I may be missing the `Manage Messages` permission.'
                    )

            if (
                    message.content.lower().startswith('is unifier down') or
                    message.content.lower().startswith('unifier not working')
            ):
                await message.channel.send('no', replies=[revolt.MessageReply(message)])

            tasks = []
            parent_id = None
            multisend = True

            if message.content.startswith('['):
                parts = message.content.replace('[', '', 1).replace('\n', ' ').split('] ', 1)
                if len(parts) > 1 and len(parts[0]) == 6:
                    if (parts[0].lower() == 'newest' or parts[0].lower() == 'recent' or
                            parts[0].lower() == 'latest'):
                        multisend = False
                    elif parts[0].lower() in list(self.bot.bridge.prs.keys()):
                        multisend = False

            pr_roomname = self.bot.config['posts_room']
            pr_ref_roomname = self.bot.config['posts_ref_room']
            is_pr = roomname == pr_roomname and (
                self.bot.config['allow_prs'] if 'allow_prs' in list(self.bot.config.keys()) else False or
                self.bot.config['allow_posts'] if 'allow_posts' in list(self.bot.config.keys()) else False
            )
            is_pr_ref = roomname == pr_ref_roomname and (
                self.bot.config['allow_prs'] if 'allow_prs' in list(self.bot.config.keys()) else False or
                self.bot.config['allow_posts'] if 'allow_posts' in list(self.bot.config.keys()) else False
            )

            should_resend = False

            if is_pr or is_pr_ref:
                multisend = False
                should_resend = True

            if multisend:
                # Multisend
                # Sends Revolt message along with other platforms to minimize
                # latency on external platforms.
                self.bot.bridge.bridged.append(self.bot.bridge.UnifierMessage(
                    author_id=message.author.id,
                    guild_id=message.server.id,
                    channel_id=message.channel.id,
                    original=message.id,
                    copies={},
                    external_copies={},
                    urls={},
                    source='revolt',
                    room=roomname,
                    external_urls={},
                    external_bridged=False
                ))
                if datetime.datetime.now().day != self.bot.bridge.msg_stats_reset:
                    self.bot.bridge.msg_stats_reset = datetime.datetime.now().day
                    self.bot.bridge.msg_stats = {}
                try:
                    self.bot.bridge.msg_stats[roomname] += 1
                except:
                    self.bot.bridge.msg_stats.update({roomname: 1})
                if self.compatibility_mode:
                    tasks.append(self.bot.loop.create_task(
                        self.bot.bridge.send(room=roomname, message=message, platform='revolt',
                                             extbridge=False)
                    ))
                else:
                    tasks.append(self.bot.loop.create_task(
                        self.bot.bridge.send(room=roomname, message=message, source='revolt', platform='revolt',
                                             extbridge=False)
                    ))
            else:
                if self.compatibility_mode:
                    parent_id = await self.bot.bridge.send(room=roomname, message=message,
                                                           platform='revolt',
                                                           extbridge=False)
                else:
                    parent_id = await self.bot.bridge.send(room=roomname, message=message, source='revolt',
                                                           platform='revolt',
                                                           extbridge=False)

            if should_resend and parent_id == message.id:
                if self.compatibility_mode:
                    tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                        room=roomname, message=message, platform='discord', extbridge=False,
                        id_override=parent_id
                    )))
                else:
                    tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                        room=roomname, message=message, source='revolt', platform='discord', extbridge=False,
                        id_override=parent_id
                    )))
            else:
                if self.compatibility_mode:
                    tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                        room=roomname, message=message, platform='discord',
                        extbridge=False
                    )))
                else:
                    tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                        room=roomname, message=message, source='revolt', platform='discord',
                        extbridge=False
                    )))

            for platform in self.bot.platforms.keys():
                if platform == 'revolt' or platform == 'discord':
                    continue
                if should_resend and parent_id == message.id:
                    if self.compatibility_mode:
                        tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                            room=roomname, message=message, platform=platform, extbridge=False,
                            id_override=parent_id
                        )))
                    else:
                        tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                            room=roomname, message=message, source='revolt', platform=platform, extbridge=False,
                            id_override=parent_id
                        )))
                else:
                    if self.compatibility_mode:
                        tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                            room=roomname, message=message, platform=platform,
                            extbridge=False
                        )))
                    else:
                        tasks.append(self.bot.loop.create_task(self.bot.bridge.send(
                            room=roomname, message=message, source='revolt', platform=platform,
                            extbridge=False
                        )))

            try:
                await asyncio.gather(*tasks)
            except:
                self.logger.exception('Something went wrong!')
                experiments = []
                for experiment in self.bot.db['experiments']:
                    if message.server.id in self.bot.db['experiments'][experiment]:
                        experiments.append(experiment)
                self.logger.info(f'Experiments: {experiments}')
                pass

            if should_delete:
                await message.delete()

        async def on_message_update(self, before, message):
            if message.author.id==self.user.id:
                return
            roomname = None
            if self.compatibility_mode:
                roomkey = 'rooms_revolt'
            else:
                roomkey = 'rooms'
            for key in self.bot.db[roomkey]:
                try:
                    if self.compatibility_mode:
                        if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
                            roomname = key
                            break
                    else:
                        if message.channel.id in str(self.bot.db['rooms'][key]['revolt'][message.server.id]):
                            roomname = key
                            break
                except:
                    pass
            if not roomname:
                return
            t = time.time()
            if message.author.id in f'{self.bot.db["banned"]}':
                if t >= self.bot.db["banned"][message.author.id]:
                    self.bot.db["banned"].pop(message.author.id)
                    self.bot.db.save_data()
                else:
                    return
            if message.server.id in f'{self.bot.db["banned"]}':
                if t >= self.bot.db["banned"][message.server.id]:
                    self.bot.db["banned"].pop(message.server.id)
                    self.bot.db.save_data()
                else:
                    return

            msgdata = await self.bot.bridge.fetch_message(message.id)

            await self.bot.bridge.edit(msgdata.id,message.content)

        async def on_message_delete(self, message):
            roomname = None
            if self.compatibility_mode:
                roomkey = 'rooms_revolt'
            else:
                roomkey = 'rooms'
            for key in self.bot.db[roomkey]:
                try:
                    if self.compatibility_mode:
                        if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
                            roomname = key
                            break
                    else:
                        if message.channel.id in str(self.bot.db['rooms'][key]['revolt'][message.server.id]):
                            roomname = key
                            break
                except:
                    continue
            if not roomname:
                return
            if message.author.id == self.user.id:
                return
            t = time.time()
            if message.author.id in f'{self.bot.db["banned"]}':
                if t >= self.bot.db["banned"][message.author.id]:
                    self.bot.db["banned"].pop(message.author.id)
                    self.bot.db.save_data()
                else:
                    return
            if message.server.id in f'{self.bot.db["banned"]}':
                if t >= self.bot.db["banned"][message.server.id]:
                    self.bot.db["banned"].pop(message.server.id)
                    self.bot.db.save_data()
                else:
                    return
            try:
                msgdata = await self.bot.bridge.fetch_message(message.id)
                if not msgdata.id==message.id:
                    raise ValueError()
            except:
                return

            await self.bot.bridge.delete_copies(msgdata.id)

        @rv_commands.group()
        async def bridge(self, ctx):
            pass

        @rv_commands.group()
        async def config(self, ctx):
            pass

        @rv_commands.group()
        async def moderation(self, ctx):
            pass

        @bridge.command(name='create-room', aliases=['make'])
        async def create_room(self,ctx,*,room=None):
            force_private = False
            if not ctx.author.id in self.bot.admins:
                if self.compatibility_mode or not self.bot.config['enable_private_rooms']:
                    embed = Embed(
                        title=f'{self.user.display_name or self.user.name} Command Error',
                        description=f':x: This command was not executed as you are not a bot administrator. Contact the owner of this bot for help.',
                        color=self.bot.colors.unifier
                    )
                    return await ctx.send(embed=Embed)
                force_private = True

            if room:
                room = room.lower()
                if not bool(re.match("^[A-Za-z0-9_-]*$", room)):
                    return await ctx.send(f'Room names may only contain alphabets, numbers, dashes, and underscores.')
                if room in list(self.bot.db['rooms'].keys()):
                    return await ctx.send(f'This room already exists!')

            private = False
            roomtype = 'private' if force_private else 'public'
            msg = None
            if not force_private and not self.compatibility_mode and self.bot.config['enable_private_rooms']:
                msg = await ctx.send(
                    (
                        'Please select the room type.\n\n'+
                        ':lock: **Private**: Make a room just for me and my buddies.\n'
                        ':globe_with_meridians: **Public**: Make a room for everyone to talk in.'
                    ),
                    interactions=revolt.MessageInteractions(
                        reactions=['\U0001F512','\U0001F310'], restrict_reactions=True
                    )
                )

                def check(message, user, _emoji_id):
                    return message.id == msg.id and user.id == ctx.author.id

                try:
                    _message, _user, emoji_id = await self.wait_for('reaction_add', check=check, timeout=60)
                except:
                    return await ctx.send('Timed out.')

                if emoji_id == '\U0001F512':
                    private = True
                    roomtype = 'private'
            elif not self.bot.config['enable_private_rooms']:
                roomtype = 'public'

            if private or force_private:
                room = None
                for _ in range(10):
                    room = roomtype + '-' + ''.join(
                        random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
                    if not room in self.bot.bridge.rooms:
                        break
                if room in self.bot.bridge.rooms:
                    if msg:
                        return await msg.edit(content='Could not generate a unique room name in 10 tries.')
                    else:
                        return await ctx.send('Could not generate a unique room name in 10 tries.')
            elif not private and not room:
                for _ in range(10):
                    room = 'public-' + ''.join(
                        random.choice(string.ascii_lowercase + string.digits) for _ in range(10))
                    if not room in self.bot.bridge.rooms:
                        break
                if room in self.bot.bridge.rooms:
                    if msg:
                        return await msg.edit(content='Could not generate a unique room name in 10 tries.')
                    else:
                        return await ctx.send('Could not generate a unique room name in 10 tries.')

            if self.compatibility_mode:
                self.bot.db['rooms'].update({room: {}})
                self.bot.db['rooms_revolt'].update({room: {}})
                self.bot.db['rules'].update({room: []})
                self.bot.db.save_data()
            else:
                self.bot.bridge.create_room(room, private=private or force_private, origin=ctx.server.id)
            if msg:
                await msg.edit(content=f'Created room `{room}`!')
            else:
                await ctx.send(f'Created room `{room}`!')

        @rv_commands.command()
        async def addrule(self, ctx, room, *, rule):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            room = room.lower()
            if not room in list(self.bot.db['rooms'].keys()):
                return await ctx.send(
                    f'This isn\'t a valid room. Run `{self.bot.command_prefix}rooms` for a full list of rooms.'
                )
            if self.compatibility_mode:
                rules = self.bot.db['rules'][room]
            else:
                rules = self.bot.db['rooms'][room]['meta']['rules']
            if len(rules) >= 25:
                return await ctx.send('You can only have up to 25 rules in a room!')
            if self.compatibility_mode:
                self.bot.db['rules'][room].append(rule)
            else:
                self.bot.db['rooms'][room]['meta']['rules'].append(rule)
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
            await ctx.send('Added rule!')

        @rv_commands.command()
        async def delrule(self, ctx, room, *, rule):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            room = room.lower()
            try:
                rule = int(rule)
                if rule <= 0:
                    raise ValueError()
            except:
                return await ctx.send('Rule must be a number higher than 0.')
            if not room in list(self.bot.db['rooms'].keys()):
                return await ctx.send(
                    'This isn\'t a valid room. Run `{self.bot.command_prefix}rooms` for a full list of rooms.'
                )
            if self.compatibility_mode:
                self.bot.db['rules'][room].pop(rule - 1)
            else:
                self.bot.db['rooms'][room]['meta']['rules'].pop(rule - 1)
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
            await ctx.send('Removed rule!')

        @rv_commands.command()
        async def roomrestrict(self, ctx, room):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            room = room.lower()
            if not room in list(self.bot.db['rooms'].keys()):
                return await ctx.send('This room does not exist!')
            if self.compatibility_mode:
                restricted = room in self.bot.db['restricted']
            else:
                restricted = self.bot.db['rooms'][room]['meta']['restricted']
            if restricted:
                if self.compatibility_mode:
                    self.bot.db['restricted'].remove(room)
                else:
                    self.bot.db['rooms'][room]['meta']['restricted'] = False
                await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
                await ctx.send(f'Unrestricted `{room}`!')
            else:
                if self.compatibility_mode:
                    self.bot.db['restricted'].append(room)
                else:
                    self.bot.db['rooms'][room]['meta']['restricted'] = True
                await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
                await ctx.send(f' Restricted `{room}`!')

        @rv_commands.command()
        async def roomlock(self, ctx, room):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            room = room.lower()
            if not room in list(self.bot.db['rooms'].keys()):
                return await ctx.send('This room does not exist!')
            if self.compatibility_mode:
                locked = room in self.bot.db['locked']
            else:
                locked = self.bot.db['rooms'][room]['meta']['locked']
            if locked:
                if self.compatibility_mode:
                    self.bot.db['locked'].remove(room)
                else:
                    self.bot.db['rooms'][room]['meta']['locked'] = False
                await ctx.send(f'Unlocked `{room}`!')
            else:
                if self.compatibility_mode:
                    self.bot.db['locked'].append(room)
                else:
                    self.bot.db['rooms'][room]['meta']['locked'] = True
                await ctx.send(f'Locked `{room}`!')
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())

        @rv_commands.command()
        async def rename(self, ctx, room, newroom):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            newroom = newroom.lower()
            if not room.lower() in list(self.bot.db['rooms'].keys()):
                return await ctx.send('This room does not exist!')
            if not bool(re.match("^[A-Za-z0-9_-]*$", newroom)):
                return await ctx.send('Room names may only contain alphabets, numbers, dashes, and underscores.')
            if newroom in list(self.bot.db['rooms'].keys()):
                return await ctx.send('This room already exists!')
            self.bot.db['rooms'].update({newroom: self.bot.db['rooms'][room]})
            self.bot.db['rooms'].pop(room)
            if self.compatibility_mode:
                self.bot.db['rules'].update({newroom: self.bot.db['rules'][room]})
                self.bot.db['rules'].pop(room)
                if room in self.bot.db['restricted']:
                    self.bot.db['restricted'].remove(room)
                    self.bot.db['restricted'].append(newroom)
                if room in self.bot.db['locked']:
                    self.bot.db['locked'].remove(room)
                    self.bot.db['locked'].append(newroom)
                if room in self.bot.db['roomemojis'].keys():
                    self.bot.db['roomemojis'].update({newroom: self.bot.db['roomemojis'][room]})
                    self.bot.db['roomemojis'].pop(room)
                if room in self.bot.db['rooms_revolt'].keys():
                    self.bot.db['rooms_revolt'].update({newroom: self.bot.db['rooms_revolt'][room]})
                    self.bot.db['rooms_revolt'].pop(room)
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
            await ctx.send('Room renamed!')

        @bridge.command(aliases=['connect','link'])
        async def bind(self,ctx,*,room):
            if not ctx.author.get_permissions().manage_channel and not ctx.author.id in self.bot.admins:
                return await ctx.send('You don\'t have the necessary permissions.')

            if self.compatibility_mode:
                data = self.bot.db['rooms'][room]
            else:
                data = self.bot.bridge.get_room(room.lower())

            invite = False
            invite_link = ''
            if not data:
                invite = True
                try:
                    # private rooms aren't on v2 and older
                    if self.compatibility_mode:
                        raise ValueError()

                    data = self.bot.bridge.get_room(
                        self.bot.bridge.get_invite(room.lower())['room']
                    )
                    invite_link = str(room.lower())
                    if data['meta']['restricted'] and not ctx.author.id in self.bot.admins:
                        return await ctx.send('Only admins can bind to restricted rooms.')
                except:
                    return await ctx.send(f'This isn\'t a valid room. Run `{self.bot.command_prefix}rooms` for a list of rooms.')

            mod_access = ctx.author.id in self.bot.moderators and self.bot.config['private_rooms_mod_access']

            if not invite:
                room = room.lower()
                if not room in self.bot.bridge.rooms:
                    return await ctx.send(
                        f'This isn\'t a valid room. Run `{self.bot.command_prefix}rooms` for a list of rooms.')
                else:
                    if not self.bot.bridge.can_join_room(room, ctx.author, platform='revolt') and not mod_access:
                        return await ctx.send('Your server does not have permissions to join this room.')
            else:
                room = self.bot.bridge.get_invite(room.lower())['room']

            if self.compatibility_mode:
                if not room in self.bot.db['rooms_revolt'].keys():
                    return await ctx.send(
                        f'You need to run `{self.bot.command_prefix}restart-revolt` on Discord for this room to be'+
                        ' available.'
                    )

            duplicate = None
            if self.compatibility_mode:
                for roomname in list(self.bot.db['rooms_revolt'].keys()):
                    # Prevent duplicate binding
                    try:
                        channel = self.bot.db['rooms_revolt'][roomname][f'{ctx.guild.id}'][0]
                        if channel == ctx.channel.id:
                            duplicate = roomname
                            break
                    except:
                        continue
            else:
                duplicate = self.bot.bridge.check_duplicate(ctx.channel, platform='revolt')

            if duplicate:
                return await ctx.send(
                    f'This channel is already linked to `{duplicate}`!\nRun `{self.bot.command_prefix}unbind {duplicate}` to unbind from it.'
                )

            try:
                try:
                    guild = data[f'{ctx.guild.id}']
                except:
                    guild = []
                if len(guild) >= 1:
                    return await ctx.send(
                        f'Your server is already linked to this room.\n**Accidentally deleted the webhook?** `{self.bot.command_prefix}unlink` it then `{self.bot.command_prefix}link` it back.')
                index = 0
                text = ''

                if self.compatibility_mode:
                    rules = self.bot.db['rules'][room]
                else:
                    rules = self.bot.db['rooms'][room]['meta']['rules']
                if len(rules) == 0:
                    text = f'No rules exist yet for this room! For now, follow the main room\'s rules.\nYou can always view rules if any get added using `{self.bot.command_prefix}rules {room}`.'
                else:
                    for rule in rules:
                        if text == '':
                            text = f'1. {rule}'
                        else:
                            text = f'{text}\n{index}. {rule}'
                        index += 1
                text = f'{text}\n\nPlease display these rules somewhere accessible.'
                embed = nextcord.Embed(title='Please agree to the room rules first:', description=text)
                embed.set_footer(text='Failure to follow room rules may result in user or server restrictions.')
                msg = await ctx.send(f'Please send "{self.bot.command_prefix}agree" to bind to the room.',embed=embed)

                def check(message):
                    return message.author.id == ctx.author.id

                try:
                    resp = await self.wait_for("message", check=check, timeout=60.0)
                except:
                    return await ctx.send('Timed out.')
                if not resp.content.lower()==f'{self.bot.command_prefix}agree':
                    return await ctx.send('Cancelled.')
                if self.compatibility_mode:
                    self.bot.db['rooms_revolt'][room].update({f'{ctx.server.id}': [ctx.channel.id]})
                    self.bot.db.save_data()
                else:
                    if invite:
                        await self.bot.bridge.accept_invite(ctx.author, invite_link, platform='revolt')

                    try:
                        await self.bot.bridge.join_room(ctx.author, room, ctx.channel, platform='revolt')
                    except self.bot.bridge.TooManyConnections:
                        return await ctx.send('Your server has reached the maximum number of allocated connections.')
                await ctx.send('Linked channel with network!')
                try:
                    await msg.pin()
                except:
                    pass
            except:
                await ctx.send('Something went wrong - check my permissions.')
                raise

        @bridge.command(aliases=['unlink', 'disconnect'])
        async def unbind(self, ctx, *, room=None):
            if not room:
                # room autodetect
                if not self.compatibility_mode:
                    room = self.bot.bridge.check_duplicate(ctx.channel, platform='revolt')
                if not room:
                    return await ctx.send('This channel is not connected to a room.')
            if not ctx.author.get_permissions().manage_channel and not ctx.author.id in self.bot.admins:
                return await ctx.send('You don\'t have the necessary permissions.')
            if not room in self.bot.db['rooms'].keys():
                return await ctx.send('This isn\'t a valid room.')
            try:
                if self.compatibility_mode:
                    self.bot.db['rooms_revolt'][room].pop(f'{ctx.server.id}')
                    self.bot.db.save_data()
                else:
                    await self.bot.bridge.leave_room(ctx.server, room, platform='revolt')
                await ctx.send('Unlinked channel from network!')
            except:
                await ctx.send('Something went wrong - check my permissions.')
                raise

        @bridge.command()
        async def disband(self, ctx, room):
            if self.compatibility_mode:
                return await ctx.send('You need Unifier v3 to use this command.')

            room = room.lower()
            if not room in self.bot.bridge.rooms:
                return await ctx.send(
                    f'This room does not exist. Run `{self.bot.command_prefix}rooms` for a list of rooms.')

            if not self.bot.bridge.can_manage_room(room, ctx.author, platform='revolt'):
                return await ctx.send('You do not have permissions to manage this room.')

            embed = Embed(title=f'Disband {room}?', description='Once the room is disbanded, it\'s gone forever!')

            msg = await ctx.send(embed=embed, interactions=revolt.MessageInteractions(
                reactions=['\U00002705', '\U0000274C'], restrict_reactions=True
            ))

            def check(message, user, _emoji_id):
                return message.id == msg.id and user.id == ctx.author.id

            try:
                _message, _user, emoji_id = await self.wait_for('reaction_add', check=check, timeout=60)
            except:
                return await ctx.send('Timed out.')

            if emoji_id == '\U0000274C':
                return await ctx.send('Aborted.')

            self.bot.bridge.delete_room(room)
            await ctx.send('Room disbanded.')

        @bridge.command()
        async def avatar(self, ctx, *, url=''):
            desc = f'You have no avatar! Run `{self.bot.command_prefix}avatar <url>` or set an avatar in your profile settings.'
            try:
                if f'{ctx.author.id}' in list(self.bot.db['avatars'].keys()):
                    avurl = self.bot.db['avatars'][f'{ctx.author.id}']
                    desc = f'You have a custom avatar! Run `{self.bot.command_prefix}avatar <url>` to change it, or run `{self.bot.command_prefix}avatar remove` to remove it.'
                else:
                    desc = f'You have a default avatar! Run `{self.bot.command_prefix}avatar <url>` to set a custom one for UniChat.'
                    avurl = ctx.author.avatar.url
            except:
                avurl = None
            if not url == '':
                avurl = url
            embed = revolt.SendableEmbed(title='This is your UniChat avatar!', description=desc, icon_url=avurl)
            if url == 'remove':
                if not f'{ctx.author.id}' in list(self.bot.db['avatars'].keys()):
                    return await ctx.send('You don\'t have a custom avatar!')
                self.bot.db['avatars'].pop(f'{ctx.author.id}')
                return await ctx.send('Custom avatar removed!')
            if not url == '':
                embed.title = 'This is how you\'ll look!'
                embed.description = 'Your avatar has been saved!'
                self.bot.db['avatars'].update({f'{ctx.author.id}': url})
                self.bot.db.save_data()
            try:
                await ctx.send(embed=embed)
            except:
                if not url == '':
                    return await ctx.send("Invalid URL!")

        @bridge.command()
        async def allocations(self, ctx):
            if not self.bot.config['enable_private_rooms']:
                return await ctx.send('Private rooms are disabled.')

            create_used = self.bot.bridge.get_rooms_count(ctx.server.id)
            conn_used = self.bot.bridge.get_connections_count(ctx.server.id)
            create_limit = self.bot.bridge.get_rooms_limit(ctx.server.id)
            conn_limit = self.bot.bridge.get_connections_limit(ctx.server.id)

            if create_limit > 0:
                create_warning = ':warning: ' if (create_used / create_limit) > 0.8 else ''
            else:
                create_warning = ''

            if conn_limit > 0:
                conn_warning = ':warning ' if (conn_used / conn_limit) > 0.8 else ''
            else:
                conn_warning = ''

            embed = Embed(
                title='Your Private Rooms allocations',
                color=self.bot.colors.unifier
            )
            embed.add_field(
                name='Private Rooms creations',
                value=create_warning + (
                    "You have **unlimited** Private Rooms creations." if create_limit == 0 else
                    f"You've used **{create_used}** out of **{create_limit}** allocated Private Rooms creations."
                )
            )
            embed.add_field(
                name='Private Rooms connections',
                value=conn_warning + (
                    "You have **unlimited** Private Rooms connections." if conn_limit == 0 else
                    f"You've used **{conn_used}** out of **{conn_limit}** allocated Private Rooms connections."
                ),
            )
            embed.add_field(
                name='Note',
                value=(
                    'You can always disband or disconnect from Private Rooms to free up allocations.\n'+
                    'Public Rooms connections don\'t count towards your Private Rooms connections usage.'
                )
            )
            await ctx.send(embed=embed)

        @bridge.command()
        async def rooms(self, ctx, index='1'):
            await self.roomlist(ctx, index)

        @bridge.command(name='private-rooms')
        async def private_rooms(self, ctx, index='1'):
            await self.roomlist(ctx, index, private=True)

        @bridge.command(aliases=['colour'])
        async def color(self, ctx, *, color=''):
            if color == '':
                try:
                    current_color = self.bot.db['colors'][f'{ctx.author.id}']
                    if current_color == '':
                        current_color = 'Default'
                        embed_color = self.bot.colors.unifier
                    elif current_color == 'inherit':
                        current_color = 'Inherit from role'
                        try:
                            embed_color = ctx.author.roles[len(ctx.author.roles) - 1].colour.replace('#', '')
                        except:
                            embed_color = None
                    else:
                        embed_color = current_color
                except:
                    current_color = 'Default'
                    embed_color = self.bot.colors.unifier
                try:
                    embed_color = 'rgb' + str(tuple(int(embed_color[i:i + 2], 16) for i in (0, 2, 4)))
                except:
                    embed_color = None
                embed = revolt.SendableEmbed(title='Your Unifier color', description=current_color, colour=embed_color)
                await ctx.send(embeds=[embed])
            elif color == 'inherit':
                self.bot.db['colors'].update({f'{ctx.author.id}': 'inherit'})
                self.bot.db.save_data()
                await ctx.send('Supported platforms will now inherit your Revolt role color.')
            else:
                try:
                    tuple(int(color.replace('#', '', 1)[i:i + 2], 16) for i in (0, 2, 4))
                except:
                    return await ctx.send('Invalid hex code!')
                self.bot.db['colors'].update({f'{ctx.author.id}': color})
                self.bot.db.save_data()
                await ctx.send('Supported platforms will now inherit the custom color.')

        @bridge.command()
        async def nickname(self, ctx, *, nickname=''):
            if len(nickname) > 30:
                return await ctx.send('Please keep your nickname within 30 characters.')
            if len(nickname) == 0:
                self.bot.db['nicknames'].pop(f'{ctx.author.id}', None)
            else:
                self.bot.db['nicknames'].update({f'{ctx.author.id}': nickname})
            self.bot.db.save_data()
            await ctx.send('Nickname updated.')

        @config.command()
        async def invites(self, ctx, room):
            if self.compatibility_mode:
                return await ctx.send('You need Unifier v3 to use this command.')

            room = room.lower()
            if not room in self.bot.bridge.rooms:
                return await ctx.send(f'This room does not exist. Run `{self.bot.command_prefix}rooms` for a list of rooms.')

            if not self.bot.bridge.can_manage_room(room, ctx.author, platform='revolt'):
                return await ctx.send('You do not have permissions to manage this room.')

            roominfo = self.bot.bridge.get_room(room)
            if not roominfo['meta']['private']:
                return await ctx.send('This is a public room!')

            invites = roominfo['meta']['private_meta']['invites']

            embed = Embed(title=f'Invites for {room}')

            success = 0
            for invite in invites:
                invite_data = self.bot.bridge.get_invite(invite)
                if not invite_data:
                    continue
                embed.add_field(
                    name=f'`{invite}`',
                    value=(
                              'Unlimited usage' if invite_data['remaining'] == 0 else
                              f'Remaining uses: {invite_data["remaining"]}'
                          ) + '\nExpiry: ' + (
                              "never" if invite_data["expire"] == 0 else f'<t:{round(invite_data["expire"])}:R>'
                          )
                )
                success += 1

            embed.description = f'{success}/20 invites created'
            try:
                await ctx.author.send(embed=embed)
            except:
                await ctx.send('Could not DM invites. Please turn your DMs on.')
            await ctx.send('Invites have been DMed.')

        @config.command(name='create-invite')
        async def create_invite(self, ctx, room, expiry='7d', max_usage='0'):
            if self.compatibility_mode:
                return await ctx.send('You need Unifier v3 to use this command.')

            if max_usage == room:
                # revolt.py is weird
                max_usage = '0'
            room = room.lower()
            if not room in self.bot.bridge.rooms:
                return await ctx.send(
                    f'This room does not exist. Run `{self.bot.command_prefix}rooms` for a list of rooms.')

            if not self.bot.bridge.can_manage_room(room, ctx.author, platform='revolt'):
                return await ctx.send('You do not have permissions to manage this room.')

            roominfo = self.bot.bridge.get_room(room)
            if not roominfo['meta']['private']:
                return await ctx.send('This is a public room!')

            infinite_enabled = ''
            if self.bot.config['permanent_invites']:
                infinite_enabled = ' Use `inf` instead for permanent invites.'

            if expiry == 'inf':
                if not self.bot.config['permanent_invites']:
                    return await ctx.send('Permanent invites are not enabled on this instance.')
                expiry = 0
            else:
                try:
                    expiry = timetoint(expiry)
                except:
                    return await ctx.send('Invalid duration! Try something like `7d` or `24h`.'+infinite_enabled)

                if expiry > 604800:
                    return await ctx.send('Invites cannot last longer than 7 days.')

                expiry += time.time()

            invite = self.bot.bridge.create_invite(room, int(max_usage), expiry)
            try:
                await ctx.author.send(f'Invite code: `{invite}`\nServers can use `{self.bot.command_prefix}bind {invite}` to join your room.')
            except:
                return await ctx.send(f'Invite was created, but it could not be DMed. Turn your DMs on, then run `{self.bot.command_prefix}invites` to view your invite.')
            await ctx.send('Invite was created, check your DMs!')

        @config.command(name='delete-invite')
        async def delete_invite(self, ctx, invite):
            if self.compatibility_mode:
                return await ctx.send('You need Unifier v3 to use this command.')

            invite = invite.lower()
            try:
                room = self.bot.bridge.get_invite(invite)['room']
            except:
                return await ctx.send('Could not find invite.')

            if not room in self.bot.bridge.rooms:
                return await ctx.send('The invite is associated with an invalid room.')

            if not self.bot.bridge.can_manage_room(room, ctx.author, platform='revolt'):
                return await ctx.send('You do not have permissions to manage this room.')

            # as invalid invites are handled above, we don't need to use try-except for this
            self.bot.bridge.delete_invite(invite)
            await ctx.send('Invite was deleted.')

        @moderation.command()
        async def delete(self, ctx, *, msg_id=None):
            """Deletes all bridged messages. Does not delete the original."""
            gbans = self.bot.db['banned']
            ct = time.time()
            if f'{ctx.author.id}' in list(gbans.keys()):
                banuntil = gbans[f'{ctx.author.id}']
                if ct >= banuntil and not banuntil == 0:
                    self.bot.db['banned'].pop(f'{ctx.author.id}')
                    self.bot.db.update()
                else:
                    return
            if f'{ctx.server.id}' in list(gbans.keys()):
                banuntil = gbans[f'{ctx.server.id}']
                if ct >= banuntil and not banuntil == 0:
                    self.bot.db['banned'].pop(f'{ctx.server.id}')
                    self.bot.db.update()
                else:
                    return
            if f'{ctx.author.id}' in list(gbans.keys()) or f'{ctx.server.id}' in list(gbans.keys()):
                return await ctx.send('Your account or your guild is currently **global restricted**.')

            try:
                msg_id = ctx.message.replies[0].id
            except:
                if not msg_id:
                    return await ctx.send('No message!')

            try:
                msg = await self.bot.bridge.fetch_message(msg_id)
            except:
                return await ctx.send('Could not find message in cache!')

            if not ctx.author.id==msg.author_id and not ctx.author.id in self.bot.moderators:
                return await ctx.send('You didn\'t send this message!')

            try:
                await self.bot.bridge.delete_parent(msg_id)
                if msg.webhook:
                    raise ValueError()
                return await ctx.send('Deleted message (parent deleted, copies will follow)')
            except:
                try:
                    deleted = await self.bot.bridge.delete_copies(msg_id)
                    return await ctx.send(f'Deleted message ({deleted} copies deleted)')
                except:
                    traceback.print_exc()
                    await ctx.send('Something went wrong.')

        @moderation.command()
        async def block(self, ctx, *, target):
            if not ctx.author.get_permissions().kick_members and not ctx.author.get_permissions().ban_members:
                return await ctx.send('You cannot restrict members/servers.')
            try:
                userid = int(target.replace('<@', '', 1).replace('!', '', 1).replace('>', '', 1))
                if userid == ctx.author.id:
                    return await ctx.send('You can\'t restrict yourself :thinking:')
                if userid == ctx.guild.id:
                    return await ctx.send('You can\'t restrict your own server :thinking:')
            except:
                userid = target
                if not len(userid) == 26:
                    return await ctx.send('Invalid user/server!')
            if userid in self.bot.moderators:
                return await ctx.send(
                    'UniChat moderators are immune to blocks!\n(Though, do feel free to report anyone who abuses this immunity.)')
            banlist = []
            if f'{ctx.guild.id}' in list(self.bot.db['blocked'].keys()):
                banlist = self.bot.db['blocked'][f'{ctx.guild.id}']
            else:
                self.bot.db['blocked'].update({f'{ctx.guild.id}': []})
            if userid in banlist:
                return await ctx.send('User/server already banned!')
            self.bot.db['blocked'][f'{ctx.guild.id}'].append(userid)
            self.bot.db.save_data()
            await ctx.send('User/server can no longer forward messages to this channel!')

        @moderation.command(aliases=['unban'])
        async def unblock(self, ctx, *, target):
            if not ctx.author.get_permissions().kick_members and not ctx.author.get_permissions().ban_members:
                return await ctx.send('You cannot unrestrict members/servers.')
            try:
                userid = int(target.replace('<@', '', 1).replace('!', '', 1).replace('>', '', 1))
            except:
                userid = target
                if not len(target) == 26:
                    return await ctx.send('Invalid user/server!')
            banlist = []
            if f'{ctx.guild.id}' in list(self.bot.db['blocked'].keys()):
                banlist = self.bot.db['blocked'][f'{ctx.guild.id}']
            if not userid in banlist:
                return await ctx.send('User/server not banned!')
            self.bot.db['blocked'][f'{ctx.guild.id}'].remove(userid)
            self.bot.db.save_data()
            await ctx.send('User/server can now forward messages to this channel!')

        async def roomlist(self, ctx, index, private=False):
            try:
                index = int(index) - 1
            except:
                index = 0
            if index < 1:
                index = 0

            msg = None
            skip_edit = False
            cooldown = time.time()

            while True:
                embed = Embed(title=f'{self.user.display_name or self.user.name} Rooms', color=self.bot.colors.unifier)

                for i in range(20*index,20*(index+1)):
                    if i >= len(self.bot.bridge.rooms):
                        break

                    room = self.bot.bridge.rooms[i]
                    roominfo = self.bot.bridge.get_room(room)
                    if (private and not roominfo['meta']['private']) or (not private and roominfo['meta']['private']):
                        continue

                    if private:
                        if not self.bot.bridge.can_access_room(room, ctx.author, platform='revolt'):
                            continue

                    if roominfo['meta']['restricted'] and not ctx.author.id in self.bot.admins:
                        continue

                    embed.add_field(name=roominfo['meta']['display_name'] or room, value=roominfo['meta']['description'] or 'No description provided')

                if len(embed.fields) == 0:
                    embed.add_field(name='No rooms',value='There\'s no rooms here!')

                maxpage = (len(self.bot.bridge.rooms) // 20) + 1
                embed.title = embed.title + f' (Page {index+1} of {maxpage})'

                if not msg:
                    msg = await ctx.send(
                        embed=embed,
                        interactions=revolt.MessageInteractions(
                            reactions=['\U00002B05\U0000FE0F', '\U000027A1\U0000FE0F'], restrict_reactions=True
                        )
                    )
                elif not skip_edit:
                    await msg.edit(embeds=[embed])

                skip_edit = False

                def check(message, user, _emoji_id):
                    return message.id == msg.id and user.id == ctx.author.id

                try:
                    _message, _user, emoji_id = await self.wait_for('reaction_add', check=check, timeout=60)
                except:
                    await msg.edit(content='Panel has expired.')
                    break

                await msg.remove_reaction(emoji_id, user=ctx.author)

                if time.time() < cooldown:
                    await ctx.send(
                        f'You\'re changing pages too fast. Try again in {round(cooldown - time.time())} seconds.',
                        replies=[revolt.MessageReply(msg)]
                    )
                    skip_edit = True
                    continue
                else:
                    cooldown = time.time() + 5

                if emoji_id == '\U00002B05\U0000FE0F':
                    if index <= 0:
                        index = 0
                    else:
                        index -= 1
                elif emoji_id == '\U000027A1\U0000FE0F':
                    if index > maxpage:
                        index = maxpage
                    else:
                        index += 1

        @moderation.command(aliases=['find'])
        async def identify(self, ctx):
            if (not ctx.author.get_permissions().kick_members and not ctx.author.get_permissions().ban_members and
                    not ctx.author.id in self.bot.moderators):
                return
            try:
                msg = ctx.message.replies[0]
                if msg == None:
                    msg = await ctx.channel.fetch_message(ctx.message.replies[0].id)
            except:
                try:
                    msg = await ctx.channel.fetch_message(ctx.message.reply_ids[0])
                except:
                    traceback.print_exc()
                    return await ctx.send('Invalid message!')
            try:
                msg_obj = await self.bot.bridge.fetch_message(msg.id)
            except:
                return await ctx.send('Could not find message in cache!')
            if msg_obj.source == 'discord':
                try:
                    username = self.bot.get_user(int(msg_obj.author_id)).name
                except:
                    username = '[unknown]'
                try:
                    guildname = self.bot.get_guild(int(msg_obj.guild_id)).name
                except:
                    guildname = '[unknown]'
            elif msg_obj.source == 'revolt':
                try:
                    username = self.get_user(msg_obj.author_id).name
                except:
                    username = '[unknown]'
                try:
                    guildname = self.get_server(msg_obj.guild_id).name
                except:
                    guildname = '[unknown]'
            else:
                try:
                    username = self.bot.guilded_client.get_user(msg_obj.author_id).name
                except:
                    username = '[unknown]'
                try:
                    guildname = self.bot.guilded_client.get_server(msg_obj.guild_id).name
                except:
                    guildname = '[unknown]'
            await ctx.send(
                f'Sent by @{username} ({msg_obj.author_id}) in {guildname} ({msg_obj.guild_id}, {msg_obj.source})\n\nParent ID: {msg_obj.id}')

        @rv_commands.command()
        async def addmod(self, ctx, *, userid):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            userid = userid.replace('<@', '', 1).replace('!', '', 1).replace('>', '', 1)
            user = self.get_user(userid)
            if not user:
                return await ctx.send(
                    'This is not a valid user. You can either @ping to select a user **or** use their user ID.')
            if userid in self.bot.db['moderators']:
                return await ctx.send('This user is already a moderator.')
            if userid in self.bot.admins or user.bot:
                return await ctx.send('are you fr')
            self.bot.db['moderators'].append(userid)
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
            await ctx.send(f'**{user.name}#{user.discriminator}** is now a moderator!')

        @rv_commands.command(aliases=['remmod', 'delmod'])
        async def delmod(self, ctx, *, userid):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            userid = userid.replace('<@', '', 1).replace('!', '', 1).replace('>', '', 1)
            user = self.get_user(userid)
            if not user:
                return await ctx.send(
                    'This is not a valid user. You can either @ping to select a user **or** use their user ID.')
            if not userid in self.bot.db['moderators']:
                return await ctx.send('This user is not a moderator.')
            if userid in self.bot.admins or user.bot:
                return await ctx.send('are you fr')
            self.bot.db['moderators'].remove(userid)
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
            await ctx.send(f'**{user.name}#{user.discriminator}** is no longer a moderator!')

        @rv_commands.command()
        async def about(self,ctx):
            with open('plugins/revolt.json') as file:
                pluginfo = json.load(file)

            try:
                with open('plugins/system.json') as file:
                    vinfo = json.load(file)
            except:
                vinfo = {}

            try:
                with open('boot/internal.json') as file:
                    pinfo = json.load(file)
            except:
                pinfo = {}

            terms_hyperlink = f'[Terms of Service]({self.bot.config["terms_url"]})'
            if not self.bot.config["terms_url"]:
                terms_hyperlink = 'Terms of Service (missing)'

            privacy_hyperlink = f'[Privacy Policy]({self.bot.config["privacy_url"]})'
            if not self.bot.config["privacy_url"]:
                privacy_hyperlink = 'Privacy Policy (missing)'

            embed = Embed(
                title=self.user.display_name or self.user.name,
                description=(
                    self.bot.config["custom_slogan"] or 'Powered by Unifier and Unifier Revolt Support' + '\n\n' +
                    f'{pinfo.get("product_name","unknown")} is made by '+
                    f'[{pinfo.get("maintainer","unknown")}]({pinfo.get("maintainer_profile","unknown")}), a team '+
                    'dedicated to making cross-platform communication better for everyone.'
                ),
                color=self.bot.colors.unifier
            )

            embed.add_field(
                name='View source code',
                value=f'{self.bot.config["repo"]}\n{pluginfo["repository"][:-4] if pluginfo["repository"].endswith(".git") else pluginfo["repository"]}'
            )

            embed.add_field(
                name='Legal stuff',
                value=f'{terms_hyperlink}\n{privacy_hyperlink}'
            )

            embed.set_footer(
                text=(
                    f'Unifier version {vinfo.get("version","unknown")}'+
                    f' - Revolt Support version {pluginfo.get("version","unknown")}\n'+
                    f'Using Nextcord {nextcord.__version__} and Revolt.py {revolt.__version__} on Python '+
                    f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
                )
            )
            await ctx.send(embed=embed)

        def get_all_commands(self):
            def extract_subcommands(command: Union[Command[revolt.Client], Group[revolt.Client]]):
                subcommands = []
                if type(command) is rv_commands.Group:
                    for child in command.commands:
                        subcommands += extract_subcommands(child)
                    return subcommands
                else:
                    return [command]

            __commands = list(self.commands)

            application_commands = []
            __command: Union[Command[revolt.Client], Group[revolt.Client]]
            for __command in __commands:
                application_commands += extract_subcommands(__command)

            return application_commands

        @rv_commands.command()
        async def help(self, ctx, *, query: Optional[str] = None):
            search = False
            page = False
            search_query = ''
            page_number = 0
            command_focus = None
            limit = 20

            if query:
                if query.lower().startswith('search:'):
                    query = query[7:]
                    search_query = query
                    search = True

            msg: Optional[revolt.Message] = None
            skip_edit = False
            cooldown = time.time()

            while True:
                embed = Embed(
                    title=f'{self.user.display_name or self.user.name} help',
                    description=f'Run `{self.bot.command_prefix}help <command>` to view more details of a command.',
                    color=self.bot.colors.unifier
                )

                if search:
                    commands = [
                        command for command in self.get_all_commands() if (
                            search_query.lower() in (
                                f'{command.parent.name} {command.name}' if command.parent else command.name
                            ).lower() or
                            (search_query.lower() in command.description.lower() if command.description else False) or
                            any(search_query.lower() in alias.lower() for alias in command.aliases)
                        )
                    ]

                    for command in commands:
                        try:
                            canrun = await ctx.can_run(command=command)
                        except:
                            canrun = False

                        if not canrun:
                            commands.remove(command)

                    embed.title += ' / search'
                    embed.description = f'Searching: {search_query} (**{len(commands)}** results)\n{embed.description}'
                else:
                    embed.description += (
                        f' Or, use `{self.bot.command_prefix}help search:<query>` to search for commands.'
                    )
                    commands = self.get_all_commands()

                    for command in commands:
                        try:
                            canrun = await ctx.can_run(command=command)
                        except:
                            canrun = False

                        if not canrun:
                            commands.remove(command)

                    if query and not page:
                        found = False
                        try:
                            try:
                                command_focus = self.get_command(query)
                            except KeyError:
                                command_focus = self.get_command(query.lower())
                            if type(command_focus) is rv_commands.Group:
                                raise KeyError()
                            found = True
                        except KeyError:
                            try:
                                if type(command_focus) is rv_commands.Group:
                                    # space should not exist here
                                    raise KeyError()
                                if ' ' in query:
                                    group: Union[rv_commands.Group, rv_commands.Command] = self.get_command(
                                        query.split(' ')[0]
                                    )
                                    if not type(group) is rv_commands.Group:
                                        raise KeyError()
                                    command_focus = group.get_command(query.split(' ')[1])
                                    found = True
                                else:
                                    raise KeyError()
                            except KeyError:
                                pass

                        try:
                            canrun = await ctx.can_run(command=command_focus)
                        except:
                            canrun = False

                        if not canrun or not found:
                            await ctx.send('Invalid command. Use `search:command` to look up commands.')

                if command_focus:
                    cmdname = (
                        f'{command_focus.parent.name} {command_focus.name}' if command_focus.parent else command_focus.name
                    )

                    embed.title += f' / {cmdname}'
                    embed.description = (
                        f'# `{self.bot.command_prefix}{cmdname}`\n'+
                        f'{command_focus.description or "No description provided"}'
                    )

                    if command_focus.aliases:
                        embed.add_field(
                            name='Aliases',
                            value='\n'.join([f'`{self.bot.command_prefix}{alias}`' for alias in command_focus.aliases])
                        )

                    usage = (
                        command_focus.get_usage()[1:] if command_focus.get_usage().startswith(' ') else
                        command_focus.get_usage()
                    )
                    embed.add_field(name='Usage', value=f'`{self.bot.command_prefix}{usage}`')
                    await ctx.send(embed=embed)
                    break

                commands = await self.bot.loop.run_in_executor(
                    None, lambda: sorted(
                        commands,
                        key=lambda x: f'{x.parent.name} {x.name}' if x.parent else x.name
                    )
                )

                maxpage = (len(commands) - 1) // limit

                if page_number < 0:
                    page_number = 0
                elif page_number > maxpage:
                    page_number = maxpage
                offset = page_number * limit
                counted = 0
                for index in range(limit):
                    if (offset + index) >= len(commands):
                        break

                    command = commands[offset + index]
                    cmdname = (
                        f'{command.parent.name} {command.name}' if command.parent else command.name
                    )

                    embed.add_field(
                        name=f'`{self.bot.command_prefix}{cmdname}`',
                        value=command.description or 'No description provided'
                    )
                    counted += 1

                embed.set_footer(
                    text=f'Page {page_number + 1} of {maxpage + 1}'
                )

                if search:
                    embed.set_footer(
                        text=f'{embed.footer} | {offset+1} - {offset+counted} of {len(commands)} results'
                    )

                if not msg:
                    msg = await ctx.send(
                        embed=embed,
                        interactions=revolt.MessageInteractions(
                            reactions=['\U00002B05\U0000FE0F', '\U000027A1\U0000FE0F'], restrict_reactions=True
                        )
                    )
                elif not skip_edit:
                    await msg.edit(embeds=[embed])

                skip_edit = False

                def check(message, user, _emoji_id):
                    return message.id == msg.id and user.id == ctx.author.id

                try:
                    _message, _user, emoji_id = await self.wait_for('reaction_add', check=check, timeout=60)
                except:
                    await msg.edit(content='Panel has expired.')
                    break

                await msg.remove_reaction(emoji_id, user=ctx.author)

                if time.time() < cooldown:
                    await ctx.send(
                        f'You\'re changing pages too fast. Try again in {round(cooldown - time.time())} seconds.',
                        replies=[revolt.MessageReply(msg)]
                    )
                    skip_edit = True
                    continue
                else:
                    cooldown = time.time() + 5

                if emoji_id == '\U00002B05\U0000FE0F':
                    if page_number <= 0:
                        page_number = 0
                    else:
                        page_number -= 1
                elif emoji_id == '\U000027A1\U0000FE0F':
                    if page_number > maxpage:
                        page_number = maxpage
                    else:
                        page_number += 1

    async def revolt_boot(self):
        if self.bot.revolt_client is None:
            if not hasattr(self.bot, 'platforms_former'):
                self.logger.warning('Revolt Support is starting in legacy mode (non-NUPS).')
                self.logger.info('Syncing Revolt rooms...')
                for key in self.bot.db['rooms']:
                    if not key in list(self.bot.db['rooms_revolt'].keys()):
                        self.bot.db['rooms_revolt'].update({key: {}})
                        self.logger.debug('Synced room '+key)
                self.bot.db.save_data()
            while True:
                async with aiohttp.ClientSession() as session:
                    self.bot.revolt_session = session

                    if self.__tokenstore:
                        # v3.8.0 and above w/ restrictive tokenstore
                        self.bot.revolt_client = self.Client(session, self.__tokenstore.retrieve('TOKEN_REVOLT'), help_command=None)
                    elif hasattr(self.bot, 'tokenstore'):
                        # v3.2.0 and above w/ normal tokenstore
                        self.bot.revolt_client = self.Client(session, self.bot.tokenstore.retrieve('TOKEN_REVOLT'), help_command=None)
                    else:
                        # older versions w/o token encryption
                        self.bot.revolt_client = self.Client(session, os.environ.get('TOKEN_REVOLT'), help_command=None)
                    self.bot.revolt_client.add_bot(self.bot)
                    self.bot.revolt_client.add_logger(log.buildlogger(self.bot.package, 'revolt.client', self.bot.loglevel))
                    self.logger.info('Booting Revolt client...')
                    try:
                        await self.bot.revolt_client.start()
                    except Exception as e:
                        if not type(e) is RuntimeError and not str(e)=='Session is closed':
                            self.logger.exception('Revolt client failed to boot!')
                        else:
                            break
                self.logger.warn('Revolt client has exited. Rebooting in 5 seconds...')
                try:
                    await asyncio.sleep(5)
                except:
                    self.logger.error('Couldn\'t sleep, exiting loop...')
                    break

    @commands.command(name='stop-revolt', hidden=True)
    async def stop_revolt(self, ctx):
        """Kills the Revolt client. This is automatically done when upgrading Unifier."""
        if not ctx.author.id == self.bot.config['owner']:
            return
        try:
            await self.bot.revolt_session.close()
            self.bot.revolt_client_task.cancel()
            del self.bot.revolt_client
            del self.bot.revolt_session
            del self.bot.revolt_client_task
            self.bot.unload_extension('cogs.bridge_revolt')
            await ctx.send(f'Revolt client stopped.\nTo restart, run `{self.bot.command_prefix}load revolt`')
        except:
            self.logger.exception('Something went wrong!')
            await ctx.send('Something went wrong while killing the instance.')

    @commands.command(name='restart-revolt', hidden=True)
    async def restart_revolt(self, ctx):
        """Restarts the Revolt client."""
        if not ctx.author.id == self.bot.config['owner']:
            return
        try:
            await self.bot.revolt_session.close()
            self.bot.revolt_client_task.cancel()
            del self.bot.revolt_client
            del self.bot.revolt_session
            del self.bot.revolt_client_task
            self.bot.reload_extension('cogs.bridge_revolt')
            await ctx.send('Revolt client restarted.')
        except:
            self.logger.exception('Something went wrong!')
            await ctx.send('Something went wrong while restarting the instance.')

def setup(bot, tokenstore=None):
    bot.add_cog(Revolt(bot, tokenstore=tokenstore))
