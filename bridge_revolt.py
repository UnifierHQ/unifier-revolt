import ast

import discord
from discord.ext import commands
from revolt.ext import commands as rv_commands
import asyncio
import aiohttp
import revolt
import json
import traceback
import time
from time import gmtime, strftime
import hashlib
from io import BytesIO

with open('config.json', 'r') as file:
    data = json.load(file)

owner = data['owner']
external_services = data['external']

mentions = discord.AllowedMentions(everyone=False, roles=False, users=False)

def log(type='???',status='ok',content='None'):
    time1 = strftime("%Y.%m.%d %H:%M:%S", gmtime())
    if status=='ok':
        status = ' OK  '
    elif status=='error':
        status = 'ERROR'
    elif status=='warn':
        status = 'WARN '
    elif status=='info':
        status = 'INFO '
    else:
        raise ValueError('Invalid status type provided')
    print(f'[{type} | {time1} | {status}] {content}')

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

class Revolt(commands.Cog,name='<:revoltsupport:1211013978558304266> Revolt Support'):
    """An extension that enables Unifier to run on Revolt. Manages Revolt instance, as well as Revolt-to-Revolt and Revolt-to-Discord bridging.

    Developed by Green"""
    def __init__(self,bot):
        self.bot = bot
        if not 'revolt' in external_services:
            raise RuntimeError('revolt is not listed as an external service in config.json. More info: https://unichat-wiki.pixels.onl/setup-selfhosted/getting-started#installing-revolt-support')
        if not hasattr(self.bot, 'revolt_client'):
            self.bot.revolt_client = None
            self.bot.revolt_session = None
            self.revolt_client_task = asyncio.create_task(self.revolt_boot())

    def db(self):
        return self.bot.db

    class Client(rv_commands.CommandsClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.bot = None

        def add_bot(self,bot):
            """Adds a Discord bot to the Revolt client."""
            self.bot = bot

        async def get_prefix(self, message: revolt.Message):
            return self.bot.command_prefix

        async def on_ready(self):
            log('RVT','ok','Revolt client booted!')

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
            if roomname=='pr':
                return await message.channel.send('PRs aren\'t supported in Unifier for Revolt yet.')
            user_hash = encrypt_string(f'{message.author.id}')[:3]
            guild_hash = encrypt_string(f'{message.server.id}')[:3]
            ids = {}
            for guild in self.bot.db['rooms_revolt'][roomname]:
                if guild==message.server.id:
                    continue
                try:
                    guild = self.bot.revolt_client.get_server(guild)
                except:
                    continue
                if guild.id in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][guild.id]:
                        self.bot.db["banned"].pop(guild.id)
                        self.bot.db.save_data()
                    else:
                        continue
                try:
                    if message.author.id in str(self.bot.db["blocked"][f'{guild.id}']) or message.server.id in str(
                            self.bot.db["blocked"][f'{guild.id}']):
                        continue
                except:
                    pass
                ch = guild.get_channel(self.bot.db['rooms_revolt'][roomname][guild.id][0])
                identifier = ' (' + user_hash + guild_hash + ')'
                author = message.author.display_name or message.author.name
                if f'{message.author.id}' in list(self.bot.db['nicknames'].keys()):
                    author = self.bot.db['nicknames'][f'{message.author.id}']
                rvtcolor = None
                if message.author.id in list(self.bot.db['colors'].keys()):
                    color = self.bot.db['colors'][message.author.id]
                    if color == 'inherit':
                        rvtcolor = message.author.roles[0].colour
                    else:
                        rgbtuple = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
                        rvtcolor = f'rgb{rgbtuple}'
                try:
                    persona = revolt.Masquerade(name=author + identifier, avatar=message.author.avatar.url, colour=rvtcolor)
                except:
                    persona = revolt.Masquerade(name=author + identifier, avatar=None, colour=rvtcolor)
                msg_data = None
                if len(message.replies) > 0:
                    ref = message.replies[0]
                    try:
                        msg_data = self.bot.bridged_obe[f'{ref.id}'][guild.id]
                    except:
                        for key in self.bot.bridged_external:
                            if f'{ref.id}' in str(self.bot.bridged_external[key]['revolt']):
                                msg_data = self.bot.bridged_external[f'{key}']['revolt'][guild.id]
                                break
                if not msg_data:
                    replies = []
                else:
                    msg = await ch.fetch_message(msg_data)
                    replies = [revolt.MessageReply(message=msg)]
                files = []
                for attachment in message.attachments:
                    if (not 'audio' in attachment.content_type and not 'video' in attachment.content_type and
                        not 'image' in attachment.content_type) or attachment.size > 25000000:
                        continue
                    filebytes = await attachment.read()
                    files.append(revolt.File(filebytes, filename=attachment.filename))
                if message.author.bot:
                    msg = await ch.send(
                        content=message.content, embeds=message.embeds, attachments=files, replies=replies,
                        masquerade=persona
                    )
                else:
                    msg = await ch.send(content=message.content, attachments=files, replies=replies,
                                        masquerade=persona)
                ids.update({guild.id: msg.id})

            ids.update({'discord': {}, 'source': [message.server.id, message.author.id]})
            self.bot.bridged_obe.update({f'{message.id}': ids})

            threads = []
            ids = {}
            trimmed = None

            components = message.content.split('<@')
            offset = 0
            if message.content.startswith('<@'):
                offset = 1

            while offset < len(components):
                if len(components) == 1 and offset == 0:
                    break
                try:
                    userid = int(components[offset].split('>', 1)[0])
                except:
                    userid = components[offset].split('>', 1)[0]
                try:
                    user = self.get_user(userid)
                except:
                    continue
                message.content = message.content.replace(f'<@{userid}>',
                                                      f'@{user.display_name or user.name}').replace(
                    f'<@!{userid}>', f'@{user.display_name or user.name}')
                offset += 1
            discordfriendly = message.content

            for guild in self.bot.db['rooms'][roomname]:
                guild = self.bot.get_guild(int(guild))
                if not guild:
                    continue
                if f'{guild.id}' in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][f'{guild.id}']:
                        self.bot.db["banned"].pop(f'{guild.id}')
                        self.bot.db.save_data()
                    else:
                        continue
                try:
                    if message.author.id in str(self.bot.db["blocked"][f'{guild.id}']) or message.server.id in str(self.bot.db["blocked"][f'{guild.id}']):
                        continue
                except:
                    pass
                webhook = None
                try:
                    if f"{self.bot.db['rooms'][roomname][f'{guild.id}'][0]}" in list(self.bot.webhook_cache[f'{guild.id}'].keys()):
                        webhook = self.bot.webhook_cache[f'{guild.id}'][f"{self.bot.db['rooms'][roomname][str(guild.id)][0]}"]
                except:
                    webhooks = await guild.webhooks()
                    for hook in webhooks:
                        if hook.id==self.bot.db['rooms'][roomname][f'{guild.id}'][0]:
                            webhook = hook
                            break

                if not webhook:
                    continue

                components = None

                if len(message.replies) > 0:
                    ref = message.replies[0]
                    msg_id = None
                    obe = False
                    obe_author = None
                    try:
                        try:
                            msg_id = self.bot.bridged_obe[ref.id]['discord'][f'{guild.id}']
                            obe_author = self.bot.bridged_obe[ref.id]['source'][1]
                        except:
                            for key in self.bot.bridged_obe:
                                if ref.id in f'{self.bot.bridged_obe[key]}':
                                    msg_id = self.bot.bridged_obe[key]['discord'][f'{guild.id}']
                                    obe_author = self.bot.bridged_obe[key]['source'][1]
                                    break
                        if not msg_id:
                            raise ValueError()
                        obe = True
                    except:
                        for key in self.bot.bridged_external:
                            if ref.id in f'{self.bot.bridged_external[key]}':
                                msg_id = key
                                break
                    try:
                        local_msg_id = self.bot.bridged[f'{msg_id}'][f'{guild.id}']
                    except:
                        local_msg_id = msg_id
                    try:
                        url = self.bot.bridged_urls_external[f'{local_msg_id}']
                    except:
                        try:
                            url = self.bot.bridged_urls[f'{msg_id}'][f'{guild.id}']
                        except:
                            msg_id = None
                    if msg_id:
                        ref_author = '[unknown user]'
                        if obe:
                            try:
                                obe_author = self.get_user(obe_author)
                                ref_author = obe_author.display_name or obe_author.name
                            except:
                                if not ref.author.id==self.user.id:
                                    ref_author = ref.author.display_name or ref.author.name
                        else:
                            try:
                                for key in self.bot.owners:
                                    if f'{msg_id}' in f'{self.bot.owners[key]}':
                                        obe_author = self.bot.get_user(int(key))
                                        ref_author = obe_author.global_name
                                        break
                            except:
                                pass
                        if not trimmed:
                            clean_content = discord.utils.remove_markdown(ref.content)

                            components = clean_content.split('<@')
                            offset = 0
                            if clean_content.startswith('<@'):
                                offset = 1

                            while offset < len(components):
                                if len(components)==1:
                                    break
                                try:
                                    userid = int(components[offset].split('>', 1)[0])
                                except:
                                    userid = components[offset].split('>', 1)[0]
                                is_revolt = False
                                user = self.bot.get_user(userid)
                                if not user:
                                    user = self.get_user(userid)
                                    if not user:
                                        offset += 1
                                        continue
                                    is_revolt = True
                                if is_revolt:
                                    clean_content = clean_content.replace(f'<@{userid}>',
                                                                          f'@{user.display_name or user.name}').replace(
                                        f'<@!{userid}>', f'@{user.display_name or user.name}')
                                else:
                                    clean_content = clean_content.replace(f'<@{userid}>',
                                                                          f'@{user.global_name or user.name}').replace(
                                        f'<@!{userid}>', f'@{user.global_name}')
                                offset += 1
                            if len(clean_content) > 80:
                                trimmed = clean_content[:-(len(clean_content) - 77)] + '...'
                            else:
                                trimmed = clean_content
                            trimmed = trimmed.replace('\n', ' ')
                        if len(trimmed) > 0:
                            button = discord.ui.Button(
                                style=discord.ButtonStyle.red,label=trimmed,disabled=True
                            )
                        else:
                            button = discord.ui.Button(
                                style=discord.ButtonStyle.red,
                                label=f'x{len(ref.embeds) + len(ref.attachments)}',
                                emoji='\U0001F3DE', disabled=True
                            )
                        components = discord.ui.MessageComponents(
                            discord.ui.ActionRow(
                                discord.ui.Button(style=discord.ButtonStyle.url,url=url,label=f'Replying to @{ref_author}')
                            ), discord.ui.ActionRow(
                                button
                            )
                        )
                    else:
                        components = discord.ui.MessageComponents(
                            discord.ui.ActionRow(
                                discord.ui.Button(style=discord.ButtonStyle.gray,disabled=True,label='Replying to [unknown]')
                            )
                        )

                files = []
                for file in message.attachments:
                    bytes = await file.read()
                    files.append(discord.File(fp=BytesIO(bytes),filename=file.filename))

                if not message.author.avatar:
                    av_url = None
                else:
                    av_url = message.author.avatar.url

                identifier = ' (' + user_hash + guild_hash + ')'
                author = message.author.display_name or message.author.name

                msg = await webhook.send(avatar_url=av_url,username=author+identifier,
                                         content=discordfriendly,files=files,allowed_mentions=mentions,
                                         components=components,wait=True
                                         )
                self.bot.bridged_urls_external.update({f'{msg.id}':f'https://discord.com/channels/{webhook.guild_id}/{webhook.channel_id}/{msg.id}'})
                ids.update({f'{guild.id}':msg.id})

            self.bot.bridged_obe[f'{message.id}'].update(
                {'discord': ids, 'source': [message.server.id, message.author.id]})

        async def on_message_update(self, before, message):
            roomname = None
            for key in self.bot.db['rooms_revolt']:
                if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
                    roomname = key
                    break
            if not roomname:
                return
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
            for guild in self.bot.db['rooms_revolt'][roomname]:
                if guild==message.server.id:
                    continue
                try:
                    guild = self.bot.revolt_client.get_server(guild)
                except:
                    continue
                if guild.id in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][guild.id]:
                        self.bot.db["banned"].pop(guild.id)
                        self.bot.db.save_data()
                    else:
                        continue
                try:
                    if message.author.id in str(self.bot.db["blocked"][f'{guild.id}']) or message.server.id in str(
                            self.bot.db["blocked"][f'{guild.id}']):
                        continue
                except:
                    pass
                ch = guild.get_channel(self.bot.db['rooms_revolt'][roomname][guild.id][0])
                msg = await ch.fetch_message(self.bot.bridged_obe[message.id][guild.id])
                if message.author.bot:
                    await msg.edit(content=message.content, embeds=message.embeds)
                else:
                    await msg.edit(content=message.content)

            components = message.content.split('<@')
            offset = 0
            if message.content.startswith('<@'):
                offset = 1

            while offset < len(components):
                if len(components) == 1 and offset == 0:
                    break
                try:
                    userid = int(components[offset].split('>', 1)[0])
                except:
                    userid = components[offset].split('>', 1)[0]
                try:
                    user = self.get_user(userid)
                except:
                    continue
                message.content = message.content.replace(f'<@{userid}>',
                                                          f'@{user.display_name or user.name}').replace(
                    f'<@!{userid}>', f'@{user.display_name or user.name}')
                offset += 1
            discordfriendly = message.content

            for guild in self.bot.db['rooms'][roomname]:
                guild = self.bot.get_guild(int(guild))
                if not guild:
                    continue
                if f'{guild.id}' in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][f'{guild.id}']:
                        self.bot.db["banned"].pop(f'{guild.id}')
                        self.bot.db.save_data()
                    else:
                        continue
                try:
                    if message.author.id in str(self.bot.db["blocked"][f'{guild.id}']) or message.server.id in str(
                            self.bot.db["blocked"][f'{guild.id}']):
                        continue
                except:
                    pass
                webhook = None
                try:
                    if f"{self.bot.db['rooms'][roomname][f'{guild.id}'][0]}" in list(self.bot.webhook_cache[f'{guild.id}'].keys()):
                        webhook = self.bot.webhook_cache[f'{guild.id}'][f"{self.bot.db['rooms'][roomname][str(guild.id)][0]}"]
                except:
                    webhooks = await guild.webhooks()
                    for hook in webhooks:
                        if hook.id==self.bot.db['rooms'][roomname][f'{guild.id}'][0]:
                            webhook = hook
                            break

                if not webhook:
                    continue

                try:
                    if message.author.bot:
                        await webhook.edit_message(self.bot.bridged_obe[message.id]['discord'][f'{guild.id}'],
                                           content=discordfriendly,embeds=message.embeds)
                    else:
                        await webhook.edit_message(self.bot.bridged_obe[message.id]['discord'][f'{guild.id}'],
                                           content=discordfriendly)
                except:
                    continue

        async def on_message_delete(self, message):
            roomname = None
            for key in self.bot.db['rooms_revolt']:
                if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
                    roomname = key
                    break
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
            for guild in self.bot.db['rooms_revolt'][roomname]:
                if guild == message.server.id:
                    continue
                try:
                    guild = self.bot.revolt_client.get_server(guild)
                except:
                    continue
                if guild.id in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][guild.id]:
                        self.bot.db["banned"].pop(guild.id)
                        self.bot.db.save_data()
                    else:
                        continue
                try:
                    if message.author.id in f'{self.bot.db["blocked"][guild.id]}' or message.server.id in f'{self.bot.db["blocked"][guild.id]}':
                        continue
                except:
                    pass
                ch = guild.get_channel(self.bot.db['rooms_revolt'][roomname][guild.id][0])
                msg = await ch.fetch_message(self.bot.bridged_obe[message.id][guild.id])
                await msg.delete()

            for guild in self.bot.db['rooms'][roomname]:
                guild = self.bot.get_guild(int(guild))
                if not guild:
                    continue
                if f'{guild.id}' in f'{self.bot.db["banned"]}':
                    if t >= self.bot.db["banned"][f'{guild.id}']:
                        self.bot.db["banned"].pop(f'{guild.id}')
                        self.bot.db.save_data()
                    else:
                        continue
                try:
                    if message.author.id in str(self.bot.db["blocked"][f'{guild.id}']) or message.server.id in str(self.bot.db["blocked"][f'{guild.id}']):
                        continue
                except:
                    pass
                webhook = None
                try:
                    if f"{self.bot.db['rooms'][roomname][f'{guild.id}'][0]}" in list(
                            self.bot.webhook_cache[f'{guild.id}'].keys()):
                        webhook = self.bot.webhook_cache[f'{guild.id}'][
                            f"{self.bot.db['rooms'][roomname][str(guild.id)][0]}"]
                except:
                    webhooks = await guild.webhooks()
                    for hook in webhooks:
                        if hook.id == self.bot.db['rooms'][roomname][f'{guild.id}'][0]:
                            webhook = hook
                            break

                if not webhook:
                    continue

                try:
                    await webhook.delete_message(self.bot.bridged_obe[message.id]['discord'][f'{guild.id}'])
                except:
                    continue

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
                return await ctx.send(
                    'This isn\'t a valid room. Try `main`, `pr`, `prcomments`, or `liveries` instead.')
            try:
                try:
                    guild = data[f'{ctx.guild.id}']
                except:
                    guild = []
                if len(guild) >= 1:
                    return await ctx.send(
                        'Your server is already linked to this room.\n**Accidentally deleted the webhook?** `u!unlink` it then `u!link` it back.')
                index = 0
                text = ''
                if len(self.bot.db['rules'][room]) == 0:
                    text = f'No rules exist yet for this room! For now, follow the main room\'s rules.\nYou can always view rules if any get added using `u!rules {room}`.'
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
                        embed_color = ctx.author.roles[0].colour.value
                    else:
                        embed_color = ast.literal_eval('0x' + current_color)
                except:
                    current_color = 'Default'
                    embed_color = self.bot.colors.unifier
                embed_color = f'{embed_color}'.replace('0x','',1)
                embed_color = 'rgb('+str(tuple(int(embed_color[i:i + 2], 16) for i in (0, 2, 4)))+')'
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

    async def revolt_boot(self):
        if self.bot.revolt_client is None:
            log('DAT','info','Syncing Revolt rooms...')
            for key in self.bot.db['rooms']:
                if not key in list(self.bot.db['rooms_revolt'].keys()):
                    self.bot.db['rooms_revolt'].update({key: {}})
                    log('DAT','ok','Synced room '+key)
            self.bot.db.save_data()
            async with aiohttp.ClientSession() as session:
                self.bot.revolt_session = session
                self.bot.revolt_client = self.Client(session, data['revolt_token'])
                self.bot.revolt_client.add_bot(self.bot)
                log('RVT','info','Booting Revolt client...')
                try:
                    await self.bot.revolt_client.start()
                except RuntimeError:
                    pass

    @commands.command(hidden=True)
    async def send_to_revolt(self,ctx,*,message):
        if not ctx.author.id==owner:
            return
        server = self.bot.revolt_client.get_server('01HDS71G78AT18B9DEW3K6KXST')
        channel = server.get_channel('01HDS71G78TTV3J3HMX3FB180Q')
        persona = revolt.Masquerade(name="Unifier (Discord)")
        await channel.send(message,masquerade=persona)

def setup(bot):
    bot.add_cog(Revolt(bot))
