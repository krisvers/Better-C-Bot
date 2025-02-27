import asyncio
import itertools

from discord.ext import commands
import discord

from src import config as conf
from src.util import permissions

class Forums(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mapping = {}

        for channel_id, close_tag in conf.closeable.items():
            if close_tag is None:
                continue

            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.ForumChannel):
                continue

            for tag in channel.available_tags:
                if tag.name != close_tag:
                    continue
                self.mapping[channel_id] = tag

    @commands.hybrid_command(aliases=['close'], with_app_command=True)
    async def done(self, ctx: commands.Context):
        if not isinstance(ctx.channel, discord.Thread):
            return

        if ctx.channel.parent.id not in conf.closeable:
            return

        if ctx.channel.id == ctx.message.id:
            # forum starter post invokes this command
            return await ctx.send("No.")

        if ctx.author == ctx.channel.owner \
                or permissions.is_staff(ctx.author, ctx.channel) \
                or permissions.has_role(ctx.author, conf.helpful_role):

            apply_tags = {}
            if ctx.channel.parent.id in self.mapping:
                close_tag = self.mapping[ctx.channel.parent.id]
                tags = ctx.channel.applied_tags
                if close_tag not in tags:
                    tags = tags[:4]  # can only set 5 tags at a time
                    tags.insert(0, close_tag)
                    apply_tags = {'applied_tags': tags}

                    await ctx.send("Marked this thread as :white_check_mark: done.")

            await ctx.channel.edit(archived=True, **apply_tags)

    @commands.command()
    async def tohelp(self, ctx: commands.Context):
        """Move misplaced help request to #help by replying the command to the first message to be moved"""

        assert isinstance(ctx.channel, discord.TextChannel)

        assert ctx.message.reference
        msg = ctx.message.reference

        assert isinstance(msg.resolved, discord.Message)
        msg = msg.resolved

        channel: discord.ForumChannel = self.bot.get_channel(conf.help_channel)

        async def to_msg_data(message):
            msgs = []

            if message.clean_content:
                avatar = message.author.display_avatar
                author = message.author.display_name
                embed = discord.Embed(description=message.clean_content, timestamp=message.created_at).set_author(name=author, icon_url=avatar)

                msgs.append({"embeds": [embed]})

            files = await asyncio.gather(*[file.to_file() for file in message.attachments])
            if files:
                msgs.append({"files": files})

            return msgs

        msgs = [msg]
        async for message in msg.channel.history(after=msg, limit=20):
            if message.author != msg.author or message == ctx.message:
                break

            msgs.append(message)

        data = list(itertools.chain.from_iterable(await asyncio.gather(*[to_msg_data(msg) for msg in msgs])))

        thread, _ = await channel.create_thread(name = f"{msg.author.display_name}'s issue", **data.pop(0))

        for msg_data in data:
            await thread.send(**msg_data)

        # Can't delete messages older than 14 days or more than 100 at a time
        await asyncio.gather(ctx.channel.delete_messages(msgs), thread.add_user(msg.author))

        await ctx.send(f"<@{msg.author.id}> asking questions in the wrong place will get your question buried, so make sure to create a thread in our help forum. That way, you can keep track of all relevant information pertaining to your question. Your help request was thus moved to the appropriate channel under <#{thread.id}>")

async def setup(bot):
    await bot.add_cog(Forums(bot))
