import discord
from discord.ext import commands
from utils import settings
import os

bot = commands.Bot(command_prefix='!', description="A bot to assist Sailvation", case_insensitive=True)
config = settings.get('main.json')

for file in os.listdir("cogs"):
    if file.endswith(".py"):
        name = file[:-3]
        bot.load_extension(f"cogs.{name}")


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print(discord.utils.oauth_url(bot.user.id))
    game = discord.Game("Atlas")
    await bot.change_presence(activity=game)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        msg = ':exclamation: This command is on cooldown, please try again in {:.2f}s :exclamation:'.format(
            error.retry_after)
        await ctx.send(msg)
        return


bot.run(config['token'])
