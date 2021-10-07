import json
import os
import sys

from discord_slash import SlashCommand
from discord_slash.utils import manage_commands
import discord
from discord.ext import commands

token = None
admin_id = None
guild_id = None
enableVoteAll = False
minimal = False
# TODO:Sketchy Fix, Find more robust solution
botRemoved = False
ignore_webhooks = True

iniFile = "ini.json"
file = "botData.json"

karma = {}
ignored_users = []
ignored_channels = []
users_censored = []


def keys_to_int(x):
    return {int(k): v for k, v in x.items()}


def ini():
    # reads from ini file
    global token, admin_id, ignored_channels
    if not os.path.exists(iniFile):
        print("Initialization file not found")
        exit(1)
    with open(iniFile, "r") as File:
        data = json.loads(File.read())
    token = data['token']
    admin_id = data['admin_id']
    ignored_channels = data['ignored_channels']
    print("Read from ini file")

    # gets stored information on upvotes and user settings
    global karma, ignored_users, enableVoteAll, botRemoved, users_censored, minimal
    if not os.path.exists(file):
        write_to_file()
        print("Created new file " + file)
    with open(file, "r") as File:
        data = json.loads(File.read())
    karma = keys_to_int(data['karma'])
    ignored_users = data['ignored users']
    enableVoteAll = bool(data['enable vote all'])
    users_censored = data['users censored']
    minimal = data['minimal']
    print("Read from file:")
    print("Karma Score = " + str(karma))
    print("Ignored Users = " + str(ignored_users))
    print("Vote All = " + str(enableVoteAll))
    print("Censored Users = " + str(users_censored))
    print("Minimal Mode = " + str(minimal))


def write_to_file():
    data = {
        'karma': karma,
        'ignored users': ignored_users,
        'enable vote all': enableVoteAll,
        'users censored': users_censored,
        'minimal': minimal
    }
    with open(file, "w") as f:
        f.write(json.dumps(data))


ini()
activity = discord.Game(name="~help. Vote using reactions.")
if minimal:
    activity = discord.Game(name="~help. Vote by replying 'good bot'.")
bot = commands.Bot(command_prefix="~", activity=activity, intents=discord.Intents.all())
slash = SlashCommand(bot, sync_commands=True)


# noinspection PyTypeChecker
@bot.event
async def on_ready():
    global guild_id
    guild_id = list(map(lambda x: x.id, bot.guilds))
    print("Bot bot is online!")
    print(f"In guilds: {guild_id}")


@bot.event
async def on_message(message):
    global minimal
    if message.author.id in users_censored:
        await message.delete()
        print("Censored message from " + str(message.author.id) + " deleted")
        return
    # ignore webhooks
    if ignore_webhooks and message.webhook_id:
        return

    await bot.process_commands(message)
    if message.content.startswith("~"):
        return
    if (not minimal and message.author.bot or enableVoteAll) \
            and message.author.id not in ignored_users \
            and message.channel.id not in ignored_channels:
        await message.add_reaction("⬆")
        await message.add_reaction("⬇")
    if minimal and "good bot" in message.content.lower() \
            and not message.author.bot:
        if message.reference is None:
            async with message.channel.typing():
                found = False
                async for msg in message.channel.history(limit=200):
                    if msg.author.bot:
                        if msg.author.id not in karma:
                            karma[msg.author.id] = 1
                            print(f"Added user {msg.author.id}")
                        else:
                            karma[msg.author.id] += 1
                        await message.add_reaction("✅")
                        print(f"Upvoted {msg.author.id}")
                        found = True
                        break
                if not found:
                    await message.reply("Could not find a bot message within search range. Try replying to the message "
                                        "you want to upvote with `good bot`")
        else:
            authorId = message.reference.resolved.author.id
            if not message.reference.resolved.author.bot:
                return
            if authorId not in karma:
                karma[authorId] = 1
                print(f"Added user {authorId}")
            else:
                karma[authorId] += 1
            await message.reply(f"Upvoted <@{authorId}>")
            print(f"Upvoted {authorId}")
        write_to_file()


# noinspection PyUnresolvedReferences,PyTypeChecker
@slash.slash(
    name="leaderboard",
    description="Shows the leaderboard",
    options=[]
)
@bot.command(name="leaderboard", help="Shows the leaderboard for most upvoted bots")
async def leaderboard(ctx):
    print("Leaderboard has been requested")
    global karma
    guild = ctx.guild
    if len(karma) == 0:
        await ctx.send("No users added")
        return
    karma = dict(sorted(karma.items(), key=lambda item: item[1], reverse=True))
    print("Bots: " + str(len(karma)))
    print(str(karma))
    embed = discord.Embed(title="Leaderboard", description="Rankings based on upvotes", color=0x3997c6)
    user = None
    for user_id in karma:
        user = guild.get_member(user_id)
        # if user not found, might be webhook
        if user is None:
            webhooks = await guild.webhooks()
            for i in webhooks:
                if user_id == i.id:
                    user = i
                    break
        # checks if member is not in server
        if user is None:
            print(str(user_id) + f" not in guild {guild.id}")
        else:
            break

    if user is None:
        print(f"No users found in {guild.id}")
        await ctx.send("No users added in this guild")
        return

    embed.set_thumbnail(url=str(user.avatar_url))
    count = 1
    for i in list(karma):
        member = guild.get_member(i)
        if member is None:
            webhooks = await guild.webhooks()
            for j in webhooks:
                if i == j.id:
                    member = j
                    break
        # checks if member is not in server
        if member is None:
            print(str(i) + f" not in guild {guild.id}")
            continue

        embed.add_field(name=str(count) + ". " + member.name, value=karma[member.id], inline=False)
        count += 1
    await ctx.send(embed=embed)
    write_to_file()


# noinspection PyTypeChecker
@slash.slash(
    name="reset",
    description="Resets the leaderboard (Admin Required)",
    options=[]
)
@bot.command(name="reset", help="Reset the leaderboard")
async def resetLeaderboard(ctx):
    if ctx.author.id != admin_id:
        await ctx.send("Administrator privilege required")
        return
    global karma
    karma = {}
    open(file, "w").close()
    await ctx.send("Reset the leaderboard")
    print("Reset leaderboard")


# noinspection PyTypeChecker
@slash.slash(
    name="enablevoteall",
    description="Activates voting system for all messages (Admin Required)",
    options=[
        manage_commands.create_option(
            name="vote_all",
            description="Voting for all messages",
            option_type=5,
            required=True
        )
    ]
)
@bot.command(name="enablevoteall", help="Sets the option for all users to be voted")
async def enable_vote_all(ctx, vote_all: bool):
    if ctx.author.id != admin_id:
        await ctx.send("Administrator privilege required")
        return
    global enableVoteAll
    enableVoteAll = vote_all
    if vote_all:
        await ctx.send("All messages will now have a voting option")
    else:
        await ctx.send("Only bot messages will have a voting option")
    print("Vote All = " + str(enableVoteAll))


# noinspection PyTypeChecker
@slash.slash(
    name="restart",
    description="Restarts the bot (Admin Required)",
    options=[]
)
@bot.command(name="restart", help="Restarts and reloads the bot")
async def restart(ctx):
    if ctx.author.id != admin_id:
        await ctx.send("Administrator privilege required")
        return
    await ctx.send("The bot will be restarted")
    print("Bot restarted")
    os.execv(sys.executable, ['python'] + sys.argv)


@slash.slash(
    name="minimal",
    description="Activates minimalistic mode (Admin Required)",
    options=[
        manage_commands.create_option(
            name="enable",
            description="Sets minimal mode to true or false",
            option_type=5,
            required=True
        )
    ]
)
async def minimal_mode(ctx, enable: bool):
    global minimal
    if ctx.author.id != admin_id:
        await ctx.send("Administrator privilege required")
        return
    minimal = enable
    if minimal:
        await bot.change_presence(activity=discord.Game(name="~help. Vote by replying 'good bot'."))
    else:
        await bot.change_presence(activity=discord.Game(name="~help. Vote using reactions."))
    await ctx.send(f"Minimal mode set to {minimal}")


# noinspection PyTypeChecker
@slash.slash(
    name="censor",
    description="Censor a user when the conversation gets weird (Admin Required)",
    options=[
        manage_commands.create_option(
            name="censored_user",
            description="User to be censored",
            option_type=6,
            required=True
        )
    ]
)
async def censor_user(ctx, censored_user: discord.User):
    if ctx.author.id != admin_id:
        await ctx.send("Administrator privilege required")
        return
    if censored_user.id in users_censored:
        users_censored.remove(censored_user.id)
        await ctx.send("<@" + str(censored_user.id) + "> uncensored")
        print(str(censored_user.id) + " uncensored")
    else:
        users_censored.append(censored_user.id)
        await ctx.send("<@" + str(censored_user.id) + "> censored")
        print(str(censored_user.id) + " censored")
    write_to_file()


@bot.event
async def on_reaction_add(reaction, user):
    global karma, botRemoved
    emoji = reaction.emoji
    message = reaction.message

    if (emoji != "⬆" and emoji != "⬇") \
            or (not message.author.bot and not enableVoteAll) \
            or user.bot \
            or bot.user not in await reaction.users().flatten():
        return
    if enableVoteAll and message.author.id == user.id:
        botRemoved = True
        await message.remove_reaction(emoji, user)
        return

    print(message.author.name + " " + emoji)

    if emoji == "⬆":
        if karma.get(message.author.id) is None:
            karma[message.author.id] = 1
        else:
            karma[message.author.id] += 1
        for i in await next(filter(lambda r: r.emoji == "⬇", message.reactions)).users().flatten():
            if i.id == user.id:
                botRemoved = True
                await message.remove_reaction("⬇", user)
                karma[message.author.id] += 1
                break
    elif emoji == "⬇":
        if karma.get(message.author.id) is None:
            karma[message.author.id] = -1
        else:
            karma[message.author.id] -= 1
        for i in await next(filter(lambda r: r.emoji == "⬆", message.reactions)).users().flatten():
            if i.id == user.id:
                botRemoved = True
                await message.remove_reaction("⬆", user)
                karma[message.author.id] -= 1
                break
    write_to_file()


@bot.event
async def on_reaction_remove(reaction, user):
    global karma, botRemoved
    emoji = reaction.emoji
    message = reaction.message
    if (emoji != "⬆" and emoji != "⬇") \
            or (not message.author.bot and not enableVoteAll) \
            or user.bot \
            or bot.user not in await reaction.users().flatten():
        return
    if botRemoved:
        botRemoved = False
        return
    print(message.author.name + " Removed " + emoji)

    if emoji == "⬆":
        karma[message.author.id] -= 1
    elif emoji == "⬇":
        karma[message.author.id] += 1
    write_to_file()


# noinspection PyTypeChecker
@slash.slash(
    name="ignore",
    description="Removes mentioned user from voting system (Admin Required)",
    options=[
        manage_commands.create_option(
            name="user_ignored",
            description="User to be removed from voting system",
            option_type=6,
            required=True
        )
    ]
)
@bot.command(name="ignore", help="Ignores a user to be voted")
async def ignore_user(ctx, user_ignored: discord.User):
    if ctx.author.id != admin_id:
        await ctx.send("Administrator privilege required")
        return

    # remove from current leaderboard array
    if user_ignored.id in karma:
        del karma[user_ignored.id]

    # add to ignored array and save preference to file
    global ignored_users
    if user_ignored.id in ignored_users:
        ignored_users.remove(user_ignored.id)
        await ctx.send("<@" + str(user_ignored.id) + "> not ignored")
        print("User " + str(user_ignored.id) + " unignored")
    else:
        ignored_users.append(user_ignored.id)
        await ctx.send("<@" + str(user_ignored.id) + "> ignored")
        print("User " + str(user_ignored.id) + " ignored")

    write_to_file()


bot.run(token)