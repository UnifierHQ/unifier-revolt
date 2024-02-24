import discord
from discord.ext import commands
import asyncio
import aiohttp
import revolt
import json
from time import gmtime, strftime

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

    class Client(revolt.Client):
        async def on_ready(self):
            log('RVT','ok','Revolt client booted!')

        async def on_message(self, message):
            print(message.content)

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
                log('RVT','info','Booting Revolt client...')
                await self.bot.revolt_client.start()

    @commands.command(hidden=True)
    async def send_to_revolt(self,ctx,*,message):
        if not ctx.author.id==owner:
            return
        server = self.bot.revolt_client.get_server('01HDS71G78AT18B9DEW3K6KXST')
        channel = server.get_channel('01HDS71G78TTV3J3HMX3FB180Q')
        persona = revolt.Masquerade(name="green. (discord)",avatar=ctx.author.avatar.url)
        await channel.send(message,masquerade=persona)

def setup(bot):
    bot.add_cog(Revolt(bot))
