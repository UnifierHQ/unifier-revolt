"""
Unifier - A sophisticated Discord bot uniting servers and platforms
Copyright (C) 2024  Green, ItsAsheer

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import discord
from discord.ext import commands
from revolt.ext import commands as rv_commands
import asyncio
import aiohttp
import revolt
import json
import traceback
import time
from utils import log
import hashlib
import random
import string

with open('config.json', 'r') as file:
    data = json.load(file)

owner = data['owner']
external_services = data['external']
allow_prs = data["allow_prs"]
admin_ids = data['admin_ids']
pr_room_index = data["pr_room_index"] # If this is 0, then the oldest room will be used as the PR room.
pr_ref_room_index = data["pr_ref_room_index"]

mentions = discord.AllowedMentions(everyone=False, roles=False, users=False)

def encrypt_string(hash_string):
    sha_signature = \
        hashlib.sha256(hash_string.encode()).hexdigest()
    return sha_signature

def is_user_admin(id):
    try:
        global admin_ids
        if id in admin_ids:
            return True
        else:
            return False
    except:
        print("There was an error in 'is_user_admin(id)', for security reasons permission was resulted into denying!")
        return False

def is_room_restricted(room,db):
    try:
        if room in db['restricted']:
            return True
        else:
            return False
    except:
        traceback.print_exc()
        return False

def is_room_locked(room,db):
    try:
        if room in db['locked']:
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
        if not 'revolt' in external_services:
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

        def add_bot(self,bot):
            """Adds a Discord bot to the Revolt client."""
            self.bot = bot

        def add_logger(self,logger):
            self.logger = logger

        async def get_prefix(self, message: revolt.Message):
            return self.bot.command_prefix

        async def on_ready(self):
            self.logger.info('Revolt client booted!')

        async def on_message(self, message):
            roomname = None
            for key in self.bot.db['rooms_revolt']:
                try:
                    if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
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
            if message.server.id in f'{self.bot.db["banned"]}':
                if t >= self.bot.db["banned"][message.server.id]:
                    self.bot.db["banned"].pop(message.server.id)
                    self.bot.db.save_data()
                else:
                    return
            if message.content.startswith(self.bot.command_prefix):
                return await self.process_commands(message)
            if not roomname:
                return
            await self.bot.bridge.send(room=roomname, message=message, platform='revolt')
            await self.bot.bridge.send(room=roomname, message=message, platform='discord')
            for platform in external_services:
                if platform == 'revolt':
                    continue
                await self.bot.bridge.send(room=roomname, message=message, platform=platform)

        async def on_message_update(self, before, message):
            if message.author.id==self.user.id:
                return
            roomname = None
            for key in self.bot.db['rooms_revolt']:
                try:
                    if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
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
            for key in self.bot.db['rooms_revolt']:
                try:
                    if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
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

        @rv_commands.command(aliases=['connect','federate'])
        async def bind(self,ctx,*,room):
            if not ctx.author.get_permissions().manage_channel and not is_user_admin(ctx.author.id):
                return await ctx.send('You don\'t have the necessary permissions.')
            if is_room_restricted(room, self.bot.db) and not is_user_admin(ctx.author.id):
                return await ctx.send('Only Green and ItsAsheer can bind channels to restricted rooms.')
            if room == '' or not room:  # Added "not room" as a failback
                room = 'main'
                await ctx.send('**No room was given, defaulting to main**')
            try:
                data = self.bot.db['rooms'][room]
            except:
                return await ctx.send(f'This isn\'t a valid room. Run `{self.bot.command_prefix}rooms` for a list of rooms.')
            for room in list(self.bot.db['rooms_revolt'].keys()):
                # Prevent duplicate binding
                try:
                    channel = self.bot.db['rooms_revolt'][room][f'{ctx.guild.id}'][0]
                    if channel == ctx.channel.id:
                        return await ctx.send(
                            f'This channel is already linked to `{room}`!\nRun `{self.bot.command_prefix}unbind {room}` to unbind from it.')
                except:
                    continue
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
                if len(self.bot.db['rules'][room]) == 0:
                    text = f'No rules exist yet for this room! For now, follow the main room\'s rules.\nYou can always view rules if any get added using `{self.bot.command_prefix}rules {room}`.'
                else:
                    for rule in self.bot.db['rules'][room]:
                        if text == '':
                            text = f'1. {rule}'
                        else:
                            text = f'{text}\n{index}. {rule}'
                        index += 1
                text = f'{text}\n\nPlease display these rules somewhere accessible.'
                embed = discord.Embed(title='Please agree to the room rules first:', description=text)
                embed.set_footer(text='Failure to follow room rules may result in user or server restrictions.')
                msg = await ctx.send('Please send "I agree" to bind to the room.',embed=embed)

                def check(message):
                    return message.author.id == ctx.author.id

                try:
                    resp = await self.wait_for("message", check=check, timeout=60.0)
                except:
                    return await ctx.send('Timed out.')
                if not resp.content.lower()=='i agree':
                    return await ctx.send('Cancelled.')
                data = self.bot.db['rooms_revolt'][room]
                guild = [ctx.channel.id]
                data.update({f'{ctx.server.id}': guild})
                self.bot.db['rooms_revolt'][room] = data
                self.bot.db.save_data()
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
            if not ctx.author.get_permissions().manage_channel and not is_user_admin(ctx.author.id):
                return await ctx.send('You don\'t have the necessary permissions.')
            try:
                data = self.bot.db['rooms_revolt'][room]
            except:
                return await ctx.send('This isn\'t a valid room.')
            try:
                data.pop(f'{ctx.server.id}')
                self.bot.db['rooms_revolt'][room] = data
                self.bot.db.save_data()
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
            hookfound = False
            for key in self.bot.db['rooms_revolt']:
                room_guilds = self.bot.db['rooms_revolt'][key]
                if f'{msg.channel.id}' in f'{room_guilds}':
                    hookfound = True
                    break
            if not hookfound:
                return await ctx.send('I didn\'t forward this!')
            identifier = msg.author.name.split('(')
            identifier = identifier[len(identifier) - 1].replace(')', '')
            username = msg.author.name[:-9]
            if identifier == 'system':
                return await ctx.send('This is a system message.')
            found = False
            origin_guild = None
            origin_user = None
            for guild in self.bot.guilds:
                hashed = encrypt_string(f'{guild.id}')
                guildhash = identifier[3:]
                if hashed.startswith(guildhash):
                    origin_guild = guild
                    userhash = identifier[:-3]
                    try:
                        matches = list(filter(lambda x: encrypt_string(f'{x.id}').startswith(userhash), guild.members))
                        if len(matches) == 1:
                            origin_user = matches[0]
                        else:
                            if len(matches) == 0:
                                raise ValueError()
                            text = f'Found multiple matches for {origin_guild.name} ({origin_guild.id})'
                            for match in matches:
                                text = text + '\n{match} ({match.id})'
                            return await ctx.send(text)
                        found = True
                    except:
                        continue

            if found:
                await ctx.send(f'{origin_user} ({origin_user.id}) via {origin_guild.name} ({origin_guild.id})')
            else:
                for guild in self.servers:
                    hashed = encrypt_string(f'{guild.id}')
                    guildhash = identifier[3:]
                    if hashed.startswith(guildhash):
                        for member in guild.members:
                            hashed = encrypt_string(f'{member.id}')
                            userhash = identifier[:-3]
                            if hashed.startswith(userhash):
                                return await ctx.send(
                                    f'{member.name} ({member.id}) via {guild.name} ({guild.id}, Revolt)')

                await ctx.send('Could not identify user!')

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
                embed = revolt.SendableEmbed(title='Your Revolt color', description=current_color, colour=embed_color)
                await ctx.send(embeds=[embed])
            elif color == 'inherit':
                self.bot.db['colors'].update({f'{ctx.author.id}': 'inherit'})
                self.bot.db.save_data()
                await ctx.send('Your Revolt messages will now inherit your Revolt role color.')
            else:
                try:
                    tuple(int(color.replace('#', '', 1)[i:i + 2], 16) for i in (0, 2, 4))
                except:
                    return await ctx.send('Invalid hex code!')
                self.bot.db['colors'].update({f'{ctx.author.id}': color})
                self.bot.db.save_data()
                await ctx.send('Your Revolt messages will now inherit the custom color.')

        @rv_commands.command()
        async def nickname(self, ctx, *, nickname=''):
            if len(nickname) > 23:
                return await ctx.send('Please keep your nickname within 23 characters.')
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

        #async def on_command_error(self, ctx, error):
            # Error logging because asyncio is too stubborn
            #print(type(error))
            #traceback.print_exc()

    async def revolt_boot(self):
        if self.bot.revolt_client is None:
            self.logger.info('Syncing Revolt rooms...')
            for key in self.bot.db['rooms']:
                if not key in list(self.bot.db['rooms_revolt'].keys()):
                    self.bot.db['rooms_revolt'].update({key: {}})
                    self.logger.debug('Synced room '+key)
            self.bot.db.save_data()
            while True:
                async with aiohttp.ClientSession() as session:
                    self.bot.revolt_session = session
                    self.bot.revolt_client = self.Client(session, data['revolt_token'])
                    self.bot.revolt_client.add_bot(self.bot)
                    self.bot.revolt_client.add_logger(log.buildlogger(self.bot.package, 'revolt.client', self.bot.loglevel))
                    self.logger.info('Booting Revolt client...')
                    try:
                        await self.bot.revolt_client.start()
                    except:
                        self.logger.exception('Revolt client failed to boot!')
                        break
                self.logger.warn('Revolt client has exited. Rebooting in 10 seconds...')
                try:
                    await asyncio.sleep(10)
                except:
                    self.logger.error('Couldn\'t sleep, exiting loop...')
                    break

def setup(bot):
    bot.add_cog(Revolt(bot))