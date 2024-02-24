import discord
from discord.ext import commands
from revolt.ext import commands as rv_commands
import asyncio
import aiohttp
import revolt
import json
import traceback
from time import gmtime, strftime
import hashlib

with open('config.json', 'r') as file:
    data = json.load(file)

owner = data['owner']
external_services = data['external']

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

class Revolt(commands.Cog,name='Revolt Support'):
    """An extension that enables Unifier to support Revolt. Manages Revolt instance, as well as Revolt-to-Revolt and Revolt-to-Discord bridging.

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
                if message.channel.id in str(self.bot.db['rooms_revolt'][key][message.server.id]):
                    roomname = key
                    break
            if not roomname:
                return
            user_hash = encrypt_string(f'{message.author.id}')[:3]
            guild_hash = encrypt_string(f'{message.server.id}')[:3]
            ids = {}
            for guild in self.bot.db['rooms_revolt'][roomname]:
                guild = self.bot.revolt_client.get_server(guild)
                ch = guild.get_channel(self.bot.db['rooms_revolt'][roomname][guild.id][0])
                identifier = ' (' + user_hash + guild_hash + ')'
                author = message.author.display_name
                if f'{message.author.id}' in list(self.bot.db['nicknames'].keys()):
                    author = self.bot.db['nicknames'][f'{message.author.id}']
                try:
                    persona = revolt.Masquerade(name=author + identifier, avatar=message.author.avatar.url)
                except:
                    persona = revolt.Masquerade(name=author + identifier, avatar=None)
                msg_data = None
                if len(message.replies) > 0:
                    ref = message.replies[0]
                    try:
                        try:
                            msg_data = self.bot.bridged_oob[f'{ref.id}'][guild.id]
                        except:
                            msg_data = self.bot.bridged_external[f'{ref.id}']['revolt']
                    except:
                        for key in self.bot.bridged_external:
                            if f'{ref.id}' in str(self.bot.bridged_external[key]['revolt']):
                                msg_data = self.bot.bridged_external[f'{key}']['revolt']
                                break
                if not msg_data:
                    replies = []
                else:
                    msg = await ch.fetch_message(msg_data[guild.id])
                    replies = [revolt.MessageReply(message=msg)]
                files = []
                for attachment in message.attachments:
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

            self.bot.bridged_oop.update({f'{message.id}': ids})
            if message.content.startswith(self.bot.command_prefix):
                await self.process_commands(message)

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
