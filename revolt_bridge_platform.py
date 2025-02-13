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
from typing import Union

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
            ) + '\n\n'.join([f'**{field.name}**\n{field.value}' for field in self.fields])
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

class RevoltPlatform(platform_base.PlatformBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.files_per_guild = True
        self.filesize_limit = 20000000

    def bot_id(self):
        return self.bot.user.id

    def error_is_unavoidable(self, error):
        if type(error) in [revolt.errors.Forbidden, revolt.errors.ServerError]:
            return True
        elif type(error) is revolt.errors.HTTPError:
            # if revolt.py is sane, the above statement should cover all of these errors
            # but we'll add this in here just in case it doesn't
            status_code = int(str(error))
            return status_code >= 500 or status_code == 401 or status_code == 403
        return False

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

    def display_name(self, user, message=None):
        if message:
            if not message.author.id == user.id:
                # mismatch
                return None
            return message.author.masquerade_name or user.display_name or user.name
        return user.display_name or user.name

    def user_name(self, user, message=None):
        if message:
            if not message.author.id == user.id:
                # mismatch
                return None
            return message.author.masquerade_name or user.display_name or user.name
        return user.name

    def name(self, obj):
        return obj.name

    def avatar(self, user, message=None):
        if message:
            if not message.author.id == user.id:
                # mismatch
                return None
            return message.author.masquerade_avatar.url if message.author.masquerade_avatar else (
                user.avatar.url if user.avatar else None
            )
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
        converted = []
        for i in range(len(embeds)):
            if not type(embeds[i]) is nextcord.Embed:
                continue

            embed = Embed(
                title=embeds[i].title,
                description=embeds[i].description,
                url=embeds[i].url,
                colour=embeds[i].colour.value if embeds[i].colour else None,
                icon_url=(
                    embeds[i].author.icon_url if embeds[i].author else embeds[i].thumbnail.url if embeds[i].thumbnail
                    else None
                )
            )

            for field in embeds[i].fields:
                embed.add_field(field.name, field.value)

            if embeds[i].footer:
                embed.set_footer(text=embeds[i].footer.text)

            converted.append(embed)
        return converted

    def convert_embeds_discord(self, embeds):
        converted = []
        for i in range(len(embeds)):
            embed = nextcord.Embed(
                title=embeds[i].title,
                description=embeds[i].description,
                url=embeds[i].url,
                # colour=embeds[i].colour.value (do this later)
            )
            embed.set_thumbnail(url=embeds[i].icon_url)

            converted.append(embed)
        return converted

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
            userid = components[offset].split('>', 1)[0]
            try:
                user = self.bot.get_user(userid)
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
            channelid = components[offset].split('>', 1)[0]
            try:
                try:
                    channel = self.bot.get_channel(channelid)
                except:
                    channel = await self.bot.fetch_channel(channelid)
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

        components = text.split('\n')
        newlines = []
        for line in components:
            if line.startswith('##### ') or line.startswith('###### '):
                tags = line.split(' ', 1)[0]
                line = line.replace(f'{tags} ', '-# ', 1)
            elif line.startswith('#### '):
                line = line.replace('#### ', '**', 1) + '**'
            newlines.append(line)

        text = '\n'.join(newlines)

        return text

    async def to_discord_file(self, file):
        filebytes = await file.read()
        return nextcord.File(fp=BytesIO(filebytes), filename=file.filename, force_close=False)

    async def to_platform_file(self, file: Union[nextcord.Attachment, nextcord.File]):
        if type(file) is nextcord.Attachment:
            f = await file.to_file(use_cached=True)
        else:
            f = file
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
            name = special['bridge']['name'] or 'Empty username'
            if len(name) > 32:
                name = name[:-(len(name)-32)]
                if 'emoji' in special['bridge'].keys():
                    if type(special['bridge']['emoji']) is str:
                        name = name[:-2] + ' ' + special['bridge']['emoji']
            elif 'emoji' in special['bridge'].keys():
                if type(special['bridge']['emoji']) is str:
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

            if not me.get_permissions().manage_role:
                persona.colour = None
        if not special:
            msg = await channel.send(content)
        else:
            reply_id = None
            reply = special.get('reply', None)
            source = special.get('source', 'discord')

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
                        if reply.channel_id == channel.id:
                            # noinspection PyUnresolvedReferences
                            reply_id = reply.id
                        elif reply.source == 'revolt':
                            # noinspection PyUnresolvedReferences
                            reply_id = reply.copies[channel.server.id][1]
                        else:
                            # noinspection PyUnresolvedReferences
                            reply_id = reply.external_copies['revolt'][channel.server.id][1]
                    except:
                        pass

            reply_msg = None

            if reply_id:
                try:
                    reply_msg = self.bot.get_message(reply_id)
                except:
                    try:
                        reply_msg = await channel.fetch_message(reply_id)
                    except:
                        pass

            if source == 'discord':
                newlines = []
                for line in content.split('\n'):
                    if line.startswith('-# '):
                        line = line.replace('-# ', '##### ', 1)
                    newlines.append(line)
                content = '\n'.join(newlines)

            try:
                msg = await channel.send(
                    content,
                    embeds=special['embeds'] if 'embeds' in special.keys() else None,
                    attachments=special['files'] if 'files' in special.keys() else None,
                    reply=revolt.MessageReply(reply_msg) if reply_id else None,
                    masquerade=persona
                )
            except Exception as e:
                if str(e) == 'Expected object or value':
                    msg = await channel.send(
                        content,
                        embeds=special['embeds'] if 'embeds' in special.keys() else None,
                        reply=revolt.MessageReply(reply_msg) if reply_id else None,
                        masquerade=persona
                    )
                else:
                    raise
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
