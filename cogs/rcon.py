import discord
from discord.ext import commands
import traceback
import valve.rcon
import mysql.connector
from mysql.connector import Error
import time
from utils import settings
import asyncio


class Rcon:
    def __init__(self,bot):
        self.bot = bot
        self.config = settings.get('rcon.json')
        self.db = settings.get('db.json')
        self.bot.add_listener(self.memberban,'on_member_ban')
        self.bot.add_listener(self.memberleave,'on_member_remove')
        try:
            self.db = mysql.connector.connect(
                            host = self.db['host'],
                            user = self.db['username'],
                            passwd = self.db.host['password'],
                            database = self.db['database'],
                        )
            self.mycursor = self.db.cursor()
        except Error as e :
            print ("Error while connecting to MySQL", e)  

    @commands.command(pass_context=True,description="This command whitelists the specified Steam64 Id to the server.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def whitelist(self,ctx,steam64):
        if len(steam64) != 17 or steam64.isdigit() == False:
            await ctx.send("<@{}> This is not a valid Steam64 Id.".format(ctx.author.id))
            return
        await ctx.send("<@{}> Please verify that the following Steam account is yours: http://steamcommunity.com/profiles/{}\n**If it is, do `!confirm` within a minute.**".format(ctx.author.id,steam64))
        def check(m):
            return m.content.lower() == "!confirm" and m.author.id == ctx.author.id and m.channel == ctx.message.channel
        answer1 = await self.bot.wait_for('message',check = check, timeout=60)
        if answer1 == None:
            await ctx.send("<@{}> You did not do !confirm within a minute. Please start over again.".format(ctx.author.id))
        existence = await self.check_existence(ctx.author.id, steam64)
        if existence != None:
            await ctx.send("<@{}> Your {} is already in the system. Please contact an admin if you believe this is incorrect.".format(ctx.author.id,existence))
            return		
        if await self._whitelist(steam64) == False:
            await ctx.send("<@{}> Something went wrong in the whitelisting process. Please contact an admin to fix it.".format(ctx.author.id))
            return	
        sql = "INSERT INTO sailvation (discord_id,steam64_id,timestamp) VALUES (%s,%s,%s)"
        value = (ctx.author.id,steam64,time.time()+2592000.0)
        self.mycursor.execute(sql, value)
        self.db.commit()
        await ctx.send("<@{}> You have successfully been whitelisted onto Sailvation.".format(ctx.author.id))

    async def _whitelist(self, steam64):
        try:
            for x in range(len(self.config)):
                server_address = (self.config[x]['server_address'],int(self.config[x]['server_port']))
                password = self.config[x]['password']			
                with valve.rcon.RCON(server_address, password, timeout=10,multi_part=False) as rcon:
                    print(rcon.execute("AllowPlayerToJoinNoCheck {}".format(steam64)).text)
                    rcon.close()
            return True

        except:
            return False

    async def _unwhitelist(self, steam64):
        try:
            for x in range(len(self.config)):
                server_address = (self.config[x]['server_address'],int(self.config[x]['server_port']))
                password = self.config[x]['password']			
                with valve.rcon.RCON(server_address, password, timeout=10,multi_part=False) as rcon:
                    print(rcon.execute("DisallowPlayerToJoinNoCheck {}".format(steam64)).text)
                    rcon.close()
            return True

        except:
            return False

    async def get_steam64(self,discord_id):
        sql = "SELECT * FROM sailvation WHERE discord_id = %s"
        adr = (discord_id,)
        self.mycursor.execute(sql, adr)
        myresult =self.mycursor.fetchall()
        if len(myresult) == 0: return None
        else: return myresult[0][2]

    async def check_existence(self, discord=None,steam64=None):
        sql = "SELECT * FROM sailvation WHERE discord_id = %s"
        adr = (discord,)
        self.mycursor.execute(sql, adr)
        myresult =self.mycursor.fetchall()
        if len(myresult) != 0:
            return "Discord"
        sql = "SELECT * FROM sailvation WHERE steam64_id = %s"
        adr = (steam64,)
        self.mycursor.execute(sql, adr)
        myresult = self.mycursor.fetchall()
        if len(myresult) != 0:
            return "Steam64"	 
        return None

    @commands.command(pass_context=True,description="Use this command to tell the us that you are still active.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def active(self,ctx):
        steam64 = await self.get_steam64(ctx.author.id)
        if await self.check_existence(ctx.author.id, steam64) == None:
            await ctx.send("<@{}> You aren't in the system. Please whitelist yourself with `!whitelist`".format(ctx.author.id))
            return
        await self._whitelist(steam64)
        sql = "UPDATE sailvation SET timestamp = {} WHERE discord_id = {}".format(time.time()+2592000.0,ctx.author.id)
        self.mycursor.execute(sql)
        self.db.commit()
        await ctx.send("<@{}> Thanks! Remember do this approximately every 30 days to let us know you are active".format(ctx.author.id))

    @commands.command(pass_context=True,description="Purge old members")
    @commands.has_permissions(administrator=True)
    async def purge(self,ctx):
        sql = "SELECT * FROM sailvation WHERE  timestamp < {}".format(time.time())
        self.mycursor.execute(sql)
        myresult = self.mycursor.fetchall()
        amount = len(myresult)
        for result in myresult:
            await self._unwhitelist(result[2])
            await asyncio.sleep(1)
        sql = "DELETE FROM sailvation WHERE timestamp < {}".format(time.time())
        self.mycursor.execute(sql)
        self.db.commit()
        await ctx.send("<@{}> You have successfully purged {} people.".format(ctx.author.id,amount))

    @commands.command(pass_context=True,description = "Purge old members")
    @commands.has_permissions(ban_members = True)
    async def unwhitelist(self,ctx,discord_id):
        if len(discord_id) != 18:
            await ctx.send("<@{}> This is not a valid Discord id.".format(ctx.author.id))
            return
        member = ctx.guild.get_member(int(discord_id))
        if member == None:
            await ctx.send("<@{}> This member is not in the Discord.".format(ctx.author.id))
            return
        if await self.check_existence(member.id) == None:
            await ctx.send("<@{}> {} is not whitelisted.".format(ctx.author.id,member.display_name))
            return
        steam64 = await self.get_steam64(member.id)
        if steam64 == None:
            await ctx.send("<@{}> {} is not whitelisted.".format(ctx.author.id,member.display_name))
            return
        else:
            await self._unwhitelist(steam64)
            sql = "DELETE FROM sailvation WHERE discord_id = {}".format(member.id)
            self.mycursor.execute(sql)
            self.db.commit()			
            await ctx.send('<@{}> You have successfully unwhitelisted <@{}>'.format(ctx.author.id,member.id))

    async def memberleave(self,member):
        if await self.check_existence(member.id) == None:
            return
        steam64 = await self.get_steam64(member.id)
        if steam64 == None:
            return
        else:
            await self._unwhitelist(steam64)
            sql = "DELETE FROM sailvation WHERE discord_id = {}".format(member.id)
            self.mycursor.execute(sql)
            self.db.commit()

    async def memberban(self,member):
        if await self.check_existence(member.id) == None:
            return
        steam64 = await self.get_steam64(member.id)
        if steam64 == None:
            return
        else:
            await self._ban(steam64)
            await self._unwhitelist(steam64)
            sql = "DELETE FROM sailvation WHERE discord_id = {}".format(member.id)
            self.mycursor.execute(sql)
            self.db.commit()


    async def _ban(self, steam64):
        for x in range(len(self.config)):
            try:
                server_address = (self.config[x]['server_address'],int(self.config[x]['server_port']))
                password = self.config[x]['password']			
                with valve.rcon.RCON(server_address, password, timeout=10,multi_part=False) as rcon:
                    print(rcon.execute("banplayer {}".format(steam64)))
            except:
                return False 
        return True

    async def _lookup(self,_id,_type):
        sql = "SELECT * FROM sailvation WHERE {} = %s".format(_type)
        adr = (_id,)
        self.mycursor.execute(sql, adr)
        myresult =self.mycursor.fetchall()
        if len(myresult) == 0:
            return None
        return myresult[0]

    @commands.command(pass_context=True,description="Look up individuals by Steam64 or Discord Ids")
    @commands.has_permissions(ban_members=True)
    async def lookup(self,ctx,_id):
        length = len(_id)
        if _id.isdigit() == False or (length != 18 and length != 17):
            await ctx.send(f"<@{ctx.author.id}> This is not a valid Discord or Steam64 id")
            return
        if length == 18:
            result = await self._lookup(_id,"discord_id")
        else:
            result = await self._lookup(_id,"steam64_id")
        if result == None:
            await ctx.send(f"<@{ctx.author.id}> Could not find a user with that Discord or Steam64 id")
            return
        await ctx.send(f"<@{ctx.author.id}> Here is information about the user:\n Discord: <@{result[1]}>\n Steam64: {result[2]}\n Time Expire: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result[3]))}")

    @commands.command(pass_context=True,description="Broadcast to all aservers")
    @commands.has_permissions(administrator=True)
    async def broadcast(self,ctx,*,message):
        print(message)
        try:
            for x in range(len(self.config)):
                server_address = (self.config[x]['server_address'],int(self.config[x]['server_port']))
                password = self.config[x]['password']				
                with valve.rcon.RCON(server_address, password, timeout=10,multi_part=False) as rcon:
                    print(rcon.execute("broadcast {}".format(message)).text)
                    rcon.close()
            await ctx.send(f"<@{ctx.author.id}>  You have successfully broadcasted a message.")

        except:
            return False

    @commands.command(pass_context=True,description="Verify your Steam64 account is connected")
    async def connected(self,ctx):
        sql = "SELECT * FROM sailvation WHERE discord_id = %s"
        adr = (ctx.author.id,)
        self.mycursor.execute(sql, adr)
        myresult =self.mycursor.fetchall()
        if len(myresult) == 0:
            await ctx.send(f"<@{ctx.author.id}>  You haven't whitelisted yourself yet.")
            return
        await ctx.send(f"<@{ctx.author.id}>  You have successfully whitelisted with the following id: {myresult[0][2]} Verify that is the correct Steam64 Id. ")


def setup(bot):
    bot.add_cog(Rcon(bot))		