from discord.ext import commands
import valve.rcon
import mysql.connector
from mysql.connector import Error, pooling
import time
from utils import settings
import asyncio


class Rcon(commands.Cog, name="RCON"):
    def __init__(self, bot):
        self.bot = bot
        self.config = settings.get('rcon.json')
        self.db = settings.get('db.json')
        self.bot.add_listener(self.memberban, 'on_member_ban')
        self.bot.add_listener(self.memberleave, 'on_member_remove')
        try:
            self.pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="RCON", pool_size=3,
                host=self.db['host'],
                user=self.db['username'],
                passwd=self.db['password'],
                database=self.db['database'],
            )
            conn = self.pool.get_connection()
            cur = conn.cursor()
            sql = 'CREATE TABLE IF NOT EXISTS `sailvation` (`id` int(11) NOT NULL AUTO_INCREMENT,`discord_id` varchar(18) DEFAULT NULL,`steam64_id` varchar(17) DEFAULT NULL, `timestamp` int(11) DEFAULT NULL,PRIMARY KEY (`id`))'
            cur.execute(sql)
            conn.commit()
            conn.close()
        except Error as e:
            print("Error while connecting to MySQL", e)

    @commands.command(pass_context=True, description="This command whitelists the specified Steam64 Id to the server.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def whitelist(self, ctx, steam64):
        if len(steam64) != 17 or steam64.isdigit() == False:
            await ctx.send(f"<@{ctx.author.id}> This is not a valid Steam64 Id.")
            return
        await ctx.send(
            f"<@{ctx.author.id}> Please verify that the following Steam account is yours: http://steamcommunity.com/profiles/{steam64}\n**If it is, do `!confirm` within a minute.**")

        def check(m):
            return m.content.lower() == "!confirm" and m.author.id == ctx.author.id and m.channel == ctx.message.channel

        answer1 = await self.bot.wait_for('message', check=check, timeout=60)
        if answer1 == None:
            await ctx.send(f"<@{ctx.author.id}> You did not do !confirm within a minute. Please start over again.")
        existence = await self.check_existence(ctx.author.id, steam64)
        if existence != None:
            await ctx.send(
                f"<@{ctx.author.id}> Your {existence} is already in the system. Please contact an admin if you believe this is incorrect.")
            return
        if not (await self.rcon_command(f"AllowPlayerToJoinNoCheck {steam64}")):
            await ctx.send(
                f"<@{ctx.author.id}> Something went wrong in the whitelisting process. Please contact an admin to fix it.")
            return
        sql = "INSERT INTO sailvation (discord_id,steam64_id,timestamp) VALUES (%s,%s,%s)"
        value = (ctx.author.id, steam64, time.time() + 2592000.0)
        conn = self.pool.get_connection()
        cur = conn.cursor()
        cur.execute(sql, value)
        conn.commit()
        conn.close()
        await ctx.send(f"<@{ctx.author.id}> You have successfully been whitelisted onto Sailvation.")

    async def rcon_command(self, command):
        tasks = []
        for server in self.config:
            tasks.append(self._rcon_command(server, command))
        good = await asyncio.gather(*tasks, return_exceptions=True)
        if not any(good):
            return False
        return True

    async def _rcon_command(self, server, command):
        try:
            server_address = (server['server_address'], int(server['server_port']))
            password = server['password']
            with valve.rcon.RCON(server_address, password, timeout=10, multi_part=False) as rcon:
                print(rcon.execute(command).text)
                rcon.close()
            return True
        except:
            False

    async def get_steam64(self, discord_id):
        sql = "SELECT * FROM sailvation WHERE discord_id = %s"
        adr = (discord_id,)
        conn = self.pool.get_connection()
        cur = conn.cursor()
        cur.execute(sql, adr)
        myresult = cur.fetchall()
        conn.close()
        if len(myresult) == 0:
            return None
        else:
            return myresult[0][2]

    async def check_existence(self, discord=None, steam64=None):
        conn = self.pool.get_connection()
        cur = conn.cursor()
        sql = "SELECT * FROM sailvation WHERE discord_id = %s"
        adr = (discord,)
        cur.execute(sql, adr)
        myresult = cur.fetchall()
        if len(myresult) != 0:
            conn.close()
            return "Discord"
        sql = "SELECT * FROM sailvation WHERE steam64_id = %s"
        adr = (steam64,)
        cur.execute(sql, adr)
        myresult = cur.fetchall()
        if len(myresult) != 0:
            conn.close()
            return "Steam64"
        conn.close()
        return None

    @commands.command(pass_context=True, description="Use this command to tell the us that you are still active.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def active(self, ctx):
        steam64 = await self.get_steam64(ctx.author.id)
        if await self.check_existence(ctx.author.id, steam64) == None:
            await ctx.send(f"<@{ctx.author.id}> You aren't in the system. Please whitelist yourself with `!whitelist`")
            return
        await self.rcon_command(f"AllowPlayerToJoinNoCheck {steam64}")
        conn = self.pool.get_connection()
        cur = conn.cursor()
        sql = f"UPDATE sailvation SET timestamp = {time.time() + 2592000.0} WHERE discord_id = {ctx.author.id}"
        cur.execute(sql)
        conn.commit()
        conn.close()
        await ctx.send(
            f"<@{ctx.author.id}> Thanks! Remember do this approximately every 30 days to let us know you are active")

    @commands.command(pass_context=True, description="Purge old members")
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx):
        conn = self.pool.get_connection()
        cur = conn.cursor()
        sql = f"SELECT * FROM sailvation WHERE  timestamp < {time.time()}"
        cur.execute(sql)
        myresult = cur.fetchall()
        amount = len(myresult)
        for result in myresult:
            await self.rcon_command(f"DisallowPlayerToJoinNoCheck {result[2]}")
            await asyncio.sleep(1)
        sql = f"DELETE FROM sailvation WHERE timestamp < {time.time()}"
        cur.execute(sql)
        conn.commit()
        conn.close
        await ctx.send(f"<@{ctx.author.id}> You have successfully purged {amount} people.")

    @commands.command(pass_context=True, description="Purge old members")
    @commands.has_permissions(ban_members=True)
    async def unwhitelist(self, ctx, discord_id):
        if len(discord_id) != 18:
            await ctx.send(f"<@{ctx.author.id}> This is not a valid Discord id.")
            return
        member = ctx.guild.get_member(int(discord_id))
        if member == None:
            await ctx.send(f"<@{ctx.author.id}> This member is not in the Discord.")
            return
        if await self.check_existence(member.id) == None:
            await ctx.send(f"<@{ctx.author.id}> {member.display_name} is not whitelisted.")
            return
        steam64 = await self.get_steam64(member.id)
        if steam64 == None:
            await ctx.send(f"<@{ctx.author.id}> {member.display_name} is not whitelisted.")
            return
        else:
            if not await self.rcon_command(f"DisallowPlayerToJoinNoCheck {steam64}"):
                ctx.send(f"<@{ctx.author.id}> Something has failed. {member.display_name} has not been unwhitelisted.")
            conn = self.pool.get_connection()
            cur = conn.cursor()
            sql = f"DELETE FROM sailvation WHERE discord_id = {member.id}"
            cur.execute(sql)
            conn.commit()
            conn.close()
            await ctx.send(f'<@{ctx.author.id}> You have successfully unwhitelisted <@{member.id}>')

    @commands.Cog.listener()
    async def memberleave(self, member):
        if await self.check_existence(member.id) == None:
            return
        steam64 = await self.get_steam64(member.id)
        if steam64 is None:
            return
        else:
            await self.rcon_command(f"DisallowPlayerToJoinNoCheck {steam64}")
            conn = self.pool.get_connection()
            cur = conn.cursor()
            sql = f"DELETE FROM sailvation WHERE discord_id = {member.id}"
            cur.execute(sql)
            conn.commit()
            conn.close()

    @commands.Cog.listener()
    async def memberban(self, member):
        if await self.check_existence(member.id) == None:
            return
        steam64 = await self.get_steam64(member.id)
        if steam64 == None:
            return
        else:
            await self.rcon_command(f"banplayer {steam64}")
            await self.rcon_command(f"DisallowPlayerToJoinNoCheck {steam64}")
            conn = self.pool.get_connection()
            cur = conn.cursor()
            sql = f"DELETE FROM sailvation WHERE discord_id = {member.id}"
            cur.execute(sql)
            conn.commit()
            conn.close()

    async def _lookup(self, _id, _type):
        conn = self.pool.get_connection()
        cur = conn.cursor()
        sql = "SELECT * FROM sailvation WHERE {} = %s".format(_type)
        adr = (_id,)
        cur.execute(sql, adr)
        myresult = cur.fetchall()
        conn.close()
        if len(myresult) == 0:
            return None
        return myresult[0]

    @commands.command(pass_context=True, description="Look up individuals by Steam64 or Discord Ids")
    @commands.has_permissions(ban_members=True)
    async def lookup(self, ctx, _id):
        length = len(_id)
        if _id.isdigit() == False or (length != 18 and length != 17):
            await ctx.send(f"<@{ctx.author.id}> This is not a valid Discord or Steam64 id")
            return
        if length == 18:
            result = await self._lookup(_id, "discord_id")
        else:
            result = await self._lookup(_id, "steam64_id")
        if result is None:
            await ctx.send(f"<@{ctx.author.id}> Could not find a user with that Discord or Steam64 id")
            return
        await ctx.send(
            f"<@{ctx.author.id}> Here is information about the user:\n Discord: <@{result[1]}>\n Steam64: {result[2]}\n Time Expire: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result[3]))}")


    @commands.command(pass_context=True, description="Broadcast to all aservers")
    @commands.has_permissions(administrator=True)
    async def broadcast(self, ctx, *, message):
        good = await self.rcon_command(f"broadcast {message}")
        if not any(good):
            await ctx.send(f"<@{ctx.author.id}> Broadcast has failed on one or more servers.")
            return
        await ctx.send(
            f"<@{ctx.author.id}> The follow message has successfully broadcasted on all servers: '{message}'")



    @commands.command(pass_context=True, description="Destroy Wild Dinos")
    @commands.has_permissions(administrator=True)
    async def destroywilddinos(self, ctx):
        good = await self.rcon_command("DestroyWildDinos")
        if not any(good):
            await ctx.send(f"<@{ctx.author.id}> DestroyWildDinos has failed on one or more servers.")
            return
        await ctx.send(f"<@{ctx.author.id}> DestroyWildDinos has successfully ran on all servers")


def setup(bot):
    bot.add_cog(Rcon(bot))
