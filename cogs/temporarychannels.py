from discord.ext import commands
from utils import settings


class TemporaryChannels(commands.Cog, name = "Temporary Channels"):
	def __init__(self,bot):
		self.bot = bot
		self.config = settings.get('temporarychannels.json')
		self.temporary_channels = set()

	@commands.Cog.listener()
	async def on_voice_state_update(self,member, before, after):
		if after.channel == before.channel: return 
		await self.check_channel(before.channel)
		if after.channel == None:
			return
		guild = after.channel.guild
		name = member.display_name.replace('@','@\u200b')
		if after.channel.id == int(self.config[str(guild.id)]['connect']):
			voice_channel = await guild.create_voice_channel(name=name,overwrites=None,category=after.channel.category,reason="New Temp Voice Channel Created!")
			self.temporary_channels.add(voice_channel)
			await member.move_to(voice_channel)  

	@commands.Cog.listener()
	async def on_guild_join(self,guild):
		if guild.id not in self.config:
			self.config[guild.id] = dict()
			self.config[guild.id]['connect'] = None
			settings.save(self.config, 'temporarychannels.json')
		return
	
	@commands.command(pass_context=True,description="Setup Join Channel")
	@commands.has_permissions(manage_channels=True)
	async def setup(self,ctx):
		guild = ctx.guild
		if ctx.author.voice == None:
			await ctx.send(f"<@{ctx.author.id}> Please join the voice channel you want peopel to join to create a new voice channel")
			return
		self.config[guild.id] = {"connect": str(ctx.author.voice.channel.id)}
		settings.save(self.config, 'temporarychannels.json')	
		await ctx.send(f"<@{ctx.author.id}> {ctx.author.voice.channel.name} will now be used to create temporary voice channels.")
	
	async def check_channel(self,channel): #Checks channel to see if there are members in it; and if not, deletes it
		if channel not in self.temporary_channels:
			return
		if len(channel.members) == 0:
			await channel.delete(reason="Temp channel is being deleted")	

def setup(bot):
	bot.add_cog(TemporaryChannels(bot))