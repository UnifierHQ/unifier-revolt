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

# Not to be confused with bridge_revolt.py, which manages Revolt client.
# This is a service script to provide essential functions such as

from utils import platform_base
import revolt
import nextcord
from io import BytesIO

class RevoltPlatform(platform_base.PlatformBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_tb = False

    def bot_id(self):
        return self.bot.user.id

    def get_server(self, server_id):
        return self.bot.get_server(server_id)

    def get_channel(self, channel_id):
        return self.bot.get_channel(channel_id)

    def get_user(self, user_id):
        return self.bot.get_user(user_id)

    def get_member(self, server, user_id):
        return server.get_member(user_id)

    def channel(self, message: revolt.Message):
        return message.channel

    def server(self, obj):
        return obj.server

    def content(self, message: revolt.Message):
        return message.content

    def reply(self, message: revolt.Message):
        try:
            return message.replies[0]
        except:
            return message.reply_ids[0]

    def roles(self, member):
        return member.roles

    def get_hex(self, role):
        return role.colour.lower().replace('#','',1)

    def author(self, message: revolt.Message):
        return message.author

    def embeds(self, message):
        return message.embeds

    def attachments(self, message):
        return message.attachments

    def url(self, message):
        return f'https://app.revolt.chat/server/{message.server.id}/channel/{message.channel.id}/{message.id}'

    def get_id(self, obj):
        return obj.id

    def display_name(self, user):
        return user.display_name or user.name

    def user_name(self, user):
        return user.name

    def name(self, obj):
        return obj.name

    def avatar(self, user):
        return user.avatar.url if user.avatar else None

    def permissions(self, user, channel=None):
        if channel:
            user_perms = user.get_channel_permissions(channel)
        else:
            user_perms = user.get_permissions()

        permissions = platform_base.Permissions()
        permissions.ban_members = user_perms.ban_members
        permissions.manage_channels = user_perms.manage_channel
        return permissions

    def is_bot(self, user):
        return user.bot

    def attachment_size(self, attachment):
        return attachment.size

    def attachment_type(self, attachment):
        return attachment.content_type

    def convert_embeds(self, embeds):
        for i in range(len(embeds)):
            embed = revolt.SendableEmbed(
                title=embeds[i].title,
                description=embeds[i].description,
                url=embeds[i].url,
                colour=embeds[i].colour,
                icon_url=(
                    embeds[i].author.icon_url if embeds[i].author else embeds[i].thumbnail.url if embeds[i].thumbnail
                    else None
                )
            )
            embeds[i] = embed
        return embeds

    def convert_embeds_discord(self, embeds):
        for i in range(len(embeds)):
            embed = nextcord.Embed(
                title=embeds[i].title,
                description=embeds[i].description,
                url=embeds[i].url,
                colour=embeds[i].colour
            )
            embed.set_thumbnail(url=embeds[i].icon_url)
            embeds[i] = embed
        return embeds

    async def fetch_server(self, server_id):
        return await self.bot.fetch_server(server_id)

    async def fetch_channel(self, channel_id):
        return await self.bot.fetch_channel(channel_id)

    async def fetch_message(self, channel, message_id):
        return await channel.fetch_message(message_id)

    async def make_friendly(self, text):
        if text.startswith(':') and text.endswith(':'):
            try:
                emoji_id = text.replace(':', '', 1)[:-1]
                if len(emoji_id) == 26:
                    return f'[emoji](https://autumn.revolt.chat/emojis/{emoji_id}?size=48)'
            except:
                pass

        components = text.split('<@')
        offset = 0
        if text.startswith('<@'):
            offset = 1

        while offset < len(components):
            if len(components) == 1 and offset == 0:
                break
            try:
                userid = int(components[offset].split('>', 1)[0])
            except:
                userid = components[offset].split('>', 1)[0]
            try:
                user = self.bot.revolt_client.get_user(userid)
                display_name = user.display_name
            except:
                offset += 1
                continue
            text = text.replace(f'<@{userid}>', f'@{display_name or user.name}').replace(
                f'<@!{userid}>', f'@{display_name or user.name}')
            offset += 1

        components = text.split('<#')
        offset = 0
        if text.startswith('<#'):
            offset = 1

        while offset < len(components):
            if len(components) == 1 and offset == 0:
                break
            try:
                channelid = int(components[offset].split('>', 1)[0])
            except:
                channelid = components[offset].split('>', 1)[0]
            try:
                try:
                    channel = self.bot.revolt_client.get_channel(channelid)
                except:
                    channel = await self.bot.revolt_client.fetch_channel(channelid)
                if not channel:
                    raise ValueError()
            except:
                offset += 1
                continue
            text = text.replace(f'<#{channelid}>', f'#{channel.name}').replace(
                f'<#!{channelid}>', f'#{channel.name}')
            offset += 1

        components = text.split('<:')
        offset = 0
        if text.startswith('<:'):
            offset = 1

        while offset < len(components):
            if len(components) == 1 and offset == 0:
                break
            emojiname = components[offset].split(':', 1)[0]
            emojiafter = components[offset].split(':', 1)[1].split('>')[0] + '>'
            text = text.replace(f'<:{emojiname}:{emojiafter}', f':{emojiname}\\:')
            offset += 1

        components = text.split('<a:')
        offset = 0
        if text.startswith('<a:'):
            offset = 1

        while offset < len(components):
            if len(components) == 1 and offset == 0:
                break
            emojiname = components[offset].split(':', 1)[0]
            emojiafter = components[offset].split(':', 1)[1].split('>')[0] + '>'
            text = text.replace(f'<a:{emojiname}:{emojiafter}', f':{emojiname}\\:')
            offset += 1

        return text

    async def to_discord_file(self, file):
        filebytes = await file.read()
        return nextcord.File(fp=BytesIO(filebytes), filename=file.filename, force_close=False)

    async def to_platform_file(self, file):
        f = await file.to_file(use_cached=True)
        return revolt.File(f.fp.read(), filename=f.filename)

    async def send(self, channel, content, special: dict = None):
        persona = None

        def to_color(color):
            try:
                rgbtuple = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
                return f'rgb{rgbtuple}'
            except:
                return None

        if 'bridge' in special.keys():
            name = special['bridge']['name']
            if len(name) > 32:
                name = name[:-(len(name)-32)]
                if 'emoji' in special['bridge'].keys():
                    name = name[:-2] + ' ' + special['bridge']['emoji']
            elif 'emoji' in special['bridge'].keys():
                name = name + ' ' + special['bridge']['emoji']
            persona = revolt.Masquerade(
                name=name,
                avatar=special['bridge']['avatar'] if 'avatar' in special['bridge'].keys() else None,
                colour=to_color(special['bridge']['color']) if 'color' in special['bridge'].keys() else None
            )

            try:
                me = channel.server.get_member(self.bot.user.id)
            except:
                me = await channel.server.fetch_member(self.bot.user.id)

            if not me.get_permissions().manage_roles:
                persona.colour = None
        if not special:
            msg = await channel.send(content)
        else:
            reply_id = None
            reply = special.get('reply', None)

            if reply:
                if type(reply) is revolt.Message:
                    # noinspection PyUnresolvedReferences
                    reply_id = reply.id
                elif type(reply) is str:
                    reply_id = reply
                else:
                    # probably UnifierMessage, if not then ignore
                    try:
                        # noinspection PyUnresolvedReferences
                        if reply.source == 'revolt':
                            # noinspection PyUnresolvedReferences
                            reply_id = reply.copies[channel.server.id]
                        else:
                            # noinspection PyUnresolvedReferences
                            reply_id = reply.external_copies['revolt'][channel.server.id]
                    except:
                        pass

            msg = await channel.send(
                content,
                embeds=special['embeds'] if 'embeds' in special.keys() else None,
                attachments=special['files'] if 'files' in special.keys() else None,
                replies=[revolt.MessageReply(reply_id)] if reply_id else [],
                masquerade=persona
            )
        return msg

    async def edit(self, message, content, special: dict = None):
        if not special:
            await message.edit(
                content=content
            )
        else:
            await message.edit(
                content=content,
                embeds=special['embeds'] if 'embeds' in special.keys() else None
            )

    async def delete(self, message):
        await message.delete()
