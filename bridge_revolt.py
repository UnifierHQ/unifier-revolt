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
"""

import nextcord
from nextcord.ext import commands
from revolt.ext import commands as rv_commands
import asyncio
import aiohttp
import revolt
import traceback
import time
from utils import log
import hashlib
import random
import string
from dotenv import load_dotenv
import os
import emoji as pymoji
import datetime
import re

load_dotenv() # Do not check success

if not "TOKEN_REVOLT" in os.environ:
    raise RuntimeError('No Revolt token found')

mentions = nextcord.AllowedMentions(everyone=False, roles=False, users=False)

def encrypt_string(hash_string):
    sha_signature = \
        hashlib.sha256(hash_string.encode()).hexdigest()
    return sha_signature

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

class Revolt(commands.Cog,name='<:revoltsupport:1211013978558304266> Revolt Support'):
    """An extension that enables Unifier to run on Revolt. Manages Revolt instance, as well as Revolt-to-Revolt and Revolt-to-external bridging.

    Developed by Green"""
    def __init__(self,bot):
        self.bot = bot
        if not 'revolt' in self.bot.config['external']:
            raise RuntimeError('revolt is not listed as an external service in config.json. More info: https://unichat-wiki.pixels.onl/setup-selfhosted/getting-started#installing-revolt-support')
        if not hasattr(self.bot, 'revolt_client'):
            self.bot.revolt_client = None
            self.bot.revolt_session = None
            self.bot.revolt_client_task = asyncio.create_task(self.revolt_boot())
        self.logger = log.buildlogger(self.bot.package, 'revolt.core', self.bot.loglevel)

    def db(self):
        return self.bot.db

    class Client(rv_commands.CommandsClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.bot = None
            self.logger = None
            self.compatibility_mode = False

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

            if (message.content.lower().startswith('is unifier down') or
                    message.content.lower().startswith('unifier not working')):
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

            for platform in self.bot.config['external']:
                if platform == 'revolt':
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

        @rv_commands.command()
        async def addmod(self, ctx, *, userid):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            userid = userid.replace('<@', '', 1).replace('!', '', 1).replace('>', '', 1)
            user = self.get_user(userid)
            if not user:
                return await ctx.send('Not a valid user!')
            if userid in self.bot.db['moderators']:
                return await ctx.send('This user is already a moderator!')
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
                return await ctx.send('Not a valid user!')
            if not userid in self.bot.db['moderators']:
                return await ctx.send('This user is not a moderator!')
            if userid in self.bot.admins or user.bot:
                return await ctx.send('are you fr')
            self.bot.db['moderators'].remove(userid)
            await self.bot.loop.run_in_executor(None, lambda: self.bot.db.save_data())
            await ctx.send(f'**{user.name}#{user.discriminator}** is no longer a moderator!')

        @rv_commands.command()
        async def make(self,ctx,*,room):
            if not ctx.author.id in self.bot.admins:
                return await ctx.send('You do not have the permissions to run this command.')
            room = room.lower()
            if not bool(re.match("^[A-Za-z0-9_-]*$", room)):
                return await ctx.send(f'Room names may only contain alphabets, numbers, dashes, and underscores.')
            if room in list(self.bot.db['rooms'].keys()):
                return await ctx.send(f'This room already exists!')
            if self.compatibility_mode:
                self.bot.db['rooms'].update({room: {}})
                self.bot.db['rooms_revolt'].update({room: {}})
                self.bot.db['rules'].update({room: []})
                self.bot.db.save_data()
            else:
                self.bot.bridge.create_room(room, private=False)
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

        @rv_commands.command(aliases=['connect','federate'])
        async def bind(self,ctx,*,room):
            if not ctx.author.get_permissions().manage_channel and not ctx.author.id in self.bot.admins:
                return await ctx.send('You don\'t have the necessary permissions.')
            if is_room_restricted(room, self.bot.db, self.compatibility_mode) and not ctx.author.id in self.bot.admins:
                return await ctx.send('Only admins can bind channels to restricted rooms.')
            if room == '' or not room:  # Added "not room" as a failback
                room = 'main'
                await ctx.send('**No room was given, defaulting to main**')
            try:
                data = self.bot.db['rooms'][room]
            except:
                return await ctx.send(f'This isn\'t a valid room. Run `{self.bot.command_prefix}rooms` for a list of rooms.')
            if self.compatibility_mode:
                roomkey = 'rooms_revolt'
            else:
                roomkey = 'rooms'
                if data['meta']['private']:
                    return await ctx.send('Private Rooms are not supported yet!')

            duplicate = None
            if self.compatibility_mode:
                for roomname in list(self.bot.db[roomkey].keys()):
                    # Prevent duplicate binding
                    try:
                        if self.compatibility_mode:
                            channel = self.bot.db[roomkey][roomname][f'{ctx.guild.id}'][0]
                        else:
                            channel = self.bot.db[roomkey][roomname]['revolt'][f'{ctx.guild.id}'][0]
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
                    await self.bot.bridge.join_room(ctx.author, room, ctx.channel, platform='revolt')
                await ctx.send('Linked channel with network!')
                try:
                    await msg.pin()
                except:
                    pass
            except:
                await ctx.send('Something went wrong - check my permissions.')
                raise

        @rv_commands.command(aliases=['unlink', 'disconnect'])
        async def unbind(self, ctx, *, room=''):
            if room == '':
                return await ctx.send('You must specify the room to unbind from.')
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

        @rv_commands.command()
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

        @rv_commands.command(aliases=['ban'])
        async def restrict(self, ctx, *, target):
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

        @rv_commands.command(aliases=['unban'])
        async def unrestrict(self, ctx, *, target):
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

        @rv_commands.command(aliases=['find'])
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

        @rv_commands.command(aliases=['colour'])
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
                            embed_color = ctx.author.roles[len(ctx.author.roles)-1].colour.replace('#','')
                        except:
                            embed_color = None
                    else:
                        embed_color = current_color
                except:
                    current_color = 'Default'
                    embed_color = self.bot.colors.unifier
                try:
                    embed_color = 'rgb'+str(tuple(int(embed_color[i:i + 2], 16) for i in (0, 2, 4)))
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

        @rv_commands.command()
        async def nickname(self, ctx, *, nickname=''):
            if len(nickname) > 30:
                return await ctx.send('Please keep your nickname within 30 characters.')
            if len(nickname) == 0:
                self.bot.db['nicknames'].pop(f'{ctx.author.id}', None)
            else:
                self.bot.db['nicknames'].update({f'{ctx.author.id}': nickname})
            self.bot.db.save_data()
            await ctx.send('Nickname updated.')

        @rv_commands.command()
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
                if not url=='':
                    return await ctx.send("Invalid URL!")

        @rv_commands.command()
        async def about(self,ctx):
            await ctx.send('**Unifier for Revolt**\nVersion 1.0.0, made by Green')

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
                    self.bot.revolt_client = self.Client(session, os.environ.get('TOKEN_REVOLT'))
                    self.bot.revolt_client.add_bot(self.bot)
                    self.bot.revolt_client.add_logger(log.buildlogger(self.bot.package, 'revolt.client', self.bot.loglevel))
                    self.logger.info('Booting Revolt client...')
                    try:
                        await self.bot.revolt_client.start()
                    except Exception as e:
                        if not type(e) is RuntimeError or not str(e)=='Session is closed':
                            self.logger.exception('Revolt client failed to boot!')
                        else:
                            break
                self.logger.warn('Revolt client has exited. Rebooting in 10 seconds...')
                try:
                    await asyncio.sleep(10)
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
            del self.bot.revolt_client
            del self.bot.revolt_session
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
            del self.bot.revolt_client
            del self.bot.revolt_session
            self.bot.reload_extension('cogs.bridge_revolt')
            await ctx.send('Revolt client restarted.')
        except:
            self.logger.exception('Something went wrong!')
            await ctx.send('Something went wrong while restarting the instance.')

def setup(bot):
    bot.add_cog(Revolt(bot))
