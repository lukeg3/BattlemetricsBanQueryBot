#!/usr/bin/env python3

"""
    
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    created by lukeg3

    This program uses the discord.py python wrapper for the Discord API to create a Discord bot
    that reads and responds to user commands in a specific channel or with specific user definitions.
    
    See the README.md for how to configure the config.ini file prior to running this program.

"""
# import neccesary modules
import configparser
from http import client
from lib2to3.pgen2.token import NOTEQUAL
from pickle import NONE
import discord
import requests
import os

# Read configuration file
config = configparser.ConfigParser()
config.read(os.path.abspath(__file__).replace(os.path.basename(__file__), "config.ini"))

"""Values pulled from config file loaded in"""
PREFIX = config["General"]["prefix"] #discord command prefix

DC_ADMINS = config["Discord"]["admins"].replace(" ", "").split(",") #discord admins list
DC_TOKEN = config["Discord"]["discordToken"] #discord Oauth token 
DC_TEXT_CHANNEL_ID = int(config["Discord"]["discordTextChannelId"]) #discord channel identifier
DC_TEXT_CHANNEL_NAME = config["Discord"]["discordTextChannelName"]

BM_TOKEN = config["Battlemetrics"]["battlemetricsToken"] #battlemetric api token
BM_BANLIST_ID = config["Battlemetrics"]["banListId"] #battlemetrics ban list id
BM_POLLING_INTERVAL = int(config["Battlemetrics"]["pollingInterval"]) #how often the api is polled (default 10 minutes)

HEADERS = {"Authorization" : "Bearer " + BM_TOKEN}
BANLISTURL = "https://api.battlemetrics.com/bans?filter[banList]=" + BM_BANLIST_ID + "&include=user,server"

"""Define class used for storing player information"""
class PlayerInfo:
    PLAYER_NAME     = 0
    STEAM_ID        = 1
    NUM_ACTIVE      = 2
    NUM_EXPIRED     = 3
    MOST_RECENT     = 4
    MOST_RECENT_NOTE= 5
    BMLINK          = 6
    COMMBANLINK     = 7
    def __init__(self, name, sid, na, ne, mr, mrn, bm, cbl):
        self.PLAYER_NAME = name
        self.STEAM_ID = sid
        self.NUM_ACTIVE = na
        self.NUM_EXPIRED = ne
        self.MOST_RECENT = mr
        self.MOST_RECENT_NOTE = mrn
        self.BMLINK = bm
        self.COMMBANLINK = cbl
    def name(self):
        return self.PLAYER_NAME
    def steamID(self):
        return self.STEAM_ID
    def numActive(self):
        return self.NUM_ACTIVE
    def numExpired(self):
        return self.NUM_EXPIRED
    def mostRecent(self):
        return self.MOST_RECENT
    def mostRecentNote(self):
        return self.MOST_RECENT_NOTE    
    def bmLink(self):
        return self.BMLINK
    def communityBanLink(self):
        return self.COMMBANLINK



class BMQueryBot(discord.Client):
    """ Discord Ban Bot """
    def __init__(self, **options):
        """ Initialize """
        super().__init__(**options)
        self.prevList = None

        self.event = threading.Event()
        self.thread = threading.Thread(target=self.polling_thread, args=(self.event,))
        self.thread.start()
    client = discord.Client()

    async def on_ready(self):
        """ on_ready. """
        print('Logged on as', self.user)

    async def on_message(self, message):
        """ Whenever there is a new message in the discord channel. """
        messageUpper = message.content.upper()
        
        if message.author == self.user: #if its our bots message, the bot won't respond
            return

        print(str(message.author) + ": " + str(message.content))

        """Define Discord channel commands"""

        """
        if you want anyone who has access to a Discord channel to be able to execute all the commands change the below
        if statement to:

            if message.content.startswith(PREFIX) and str(message.channel) in DC_TEXT_CHANNEL_NAME:
        
        if you want only admins to be able to use it in any channel

            if str(message.author) in DC_ADMINS and message.content.startswith(PREFIX):

        if you want only admins to be able to use it in a specific channel

            if str(message.author) in DC_ADMINS and message.content.startswith(PREFIX) and str(message.channel) in DC_TEXT_CHANNEL_NAME: 
        
        if you want anyone to use the commands anywhere
             if message.content.startswith(PREFIX):
        
        """
        if message.content.startswith(PREFIX) and str(message.channel) in DC_TEXT_CHANNEL_NAME:
            command = messageUpper[len(PREFIX):]
            """lastban needs to be implemented"""
            if command == "LASTBAN": #command DMs the user that executes the command the last ban
                print("Pulling last ban")
               # banList = get_banlist(BANLISTURL, HEADERS)
               # if banList != []:
                #    await message.author.send(embed=self.create_embed_of_ban(banList[0]))

            elif command == "HELP": #command DMs the bot commands to the user that executes the command
                print("Messaging help information")
                await message.author.send(embed=self.create_help_embed())

            elif "USER" in command: #command get users ban information from battlemetrics with their steamid and posts in channel
                try:
                    steamId = command.strip(" USER") #get just the steamid from the command
                    if len(steamId) != 17:
                        print("Invalid SteamID")
                        await message.author.send("Invalid SteamID")
                    else: 
                        print("Pulling playerid")
                        playerId = get_playerID(steamId, HEADERS)
                        if playerId != None:
                            if len(playerId) == 9:
                                playerInfoURL = "https://api.battlemetrics.com/bans?filter[player]=" + playerId + "&include=user,server"
                                print("Making user embed to channel")
                                await message.channel.send(embed=self.create_player_embed(self, playerId, playerInfoURL, HEADERS))
                            else:
                                print("PlayerID not of correct length")
                                await message.author.send("No User Profile Found, check battlemetrics")
                        else:
                            await message.author.send("No User Profile Found, check battlemetrics")
                except Exception as e:
                    print("User command exception",e)
                    return[] 

    def create_help_embed(self):
        """ Create help embed for this bot. """
        embedVar = discord.Embed(title="Discord Command List", color=0x00ff00)
        embedVar.add_field(name="!help", value="Displays this help message", inline=False)
        embedVar.add_field(name="!manualbanlistpoll", value="Manually refreshes ban list and checks for changes", inline=False)
        embedVar.add_field(name="!lastban", value="DMs you the last ban made and its information", inline=False)
        embedVar.add_field(name="!user 'steamid'", value="Searches for a players ban history by SteamID. Replace 'steamid' with the players SteamID", inline=False)
        return embedVar

    def send_embed_to_text_channel(self, embedVar):
        """ Send embed to text channel. """
        self.loop.create_task(self.get_channel(DC_TEXT_CHANNEL_ID).send(embed=embedVar))
    
    def create_player_embed(trash,self, id, url, headers):
        """Creates embed of a players ban history and information"""
        card = self.make_playercard(self, id, url, headers)
        embedVar = discord.Embed(title="Player Information", color=0x00ff00)
        embedVar.add_field(name="Player Name", value=PlayerInfo.name(card), inline=False)
        embedVar.add_field(name="SteamID", value=PlayerInfo.steamID(card), inline=False)
        embedVar.add_field(name="Number of active bans:", value=PlayerInfo.numActive(card), inline=False)
        embedVar.add_field(name="Number of expired bans:", value=PlayerInfo.numExpired(card), inline=False)
        embedVar.add_field(name="Most recent ban reason:", value=PlayerInfo.mostRecent(card), inline=False)
        embedVar.add_field(name="Most recent ban note:", value=PlayerInfo.mostRecentNote(card), inline=False)
        embedVar.add_field(name="Battlemetrics Link:", value=PlayerInfo.bmLink(card), inline=False)
        embedVar.add_field(name="Community Ban List Link:", value=PlayerInfo.communityBanLink(card), inline=False)
        return embedVar

    def make_playercard(trash, self, id, url, headers):
        """Polls battlemetrics api to get the player information 
        to make the player embed"""
        try:
            response = requests.get(url, headers=headers) 
        except Exception as e:
            print("make_playercard json exception",e)
            return []
        card = response.json()
        playerNames, steamIds, numact, numexp, recent, note, bmurl, cblink = ([] for i in range(8))
        try:
            playerNames.append(card["data"][0]["meta"]["player"])
        except Exception as e:
            print("Unknown Player Name",e)
            playerNames.append("Unknown Player")
        for i in range(10):
            if card["data"][0]["attributes"]["identifiers"][i]["type"]=="steamID":
                steamIds.append(card["data"][0]["attributes"]["identifiers"][i]["identifier"])
                break
        numact.append(card["meta"]["active"])
        numexp.append(card["meta"]["expired"])
        try:
            if card["data"][0]["type"] == "ban":
                recent.append(card["data"][0]["attributes"]["reason"])
                if card["data"][0]["attributes"]["note"] == "":
                    note.append("No Ban Note")
                else:
                    note.append(card["data"][0]["attributes"]["note"])
            else:
                recent.append("No recent bans")
                note.append("No Ban Note")
        except Exception as e:
            print("make_playercard recent ban exception",e)
            if recent[0] == None:
                recent.append("No recent bans")
            if note[0] == None:
                note.append("No ban note attached")
        bmurl.append("https://www.battlemetrics.com/rcon/players/"+id)
        cblink.append("https://communitybanlist.com/search/"+steamIds[0])
        returnList = PlayerInfo(playerNames[0], steamIds[0], numact[0], numexp[0], recent[0], note[0], bmurl[0],  cblink[0])
        return returnList


def get_playerID(steamID, headers):
    """Returns the battlemetrics player id number
    from an api request searching with a players steamID"""
    url = "https://api.battlemetrics.com/players?filter[search]=" + steamID
    try:
        response = requests.get(url, headers=headers) 
    except Exception as e:
        print("get_playerID exception", e)
        return []
    playerInfo = response.json()
    playerID = None
    for player in playerInfo["data"]:
        playerID = player["id"]
    if playerID==None:
        playerID = "Unknown Player"
    return playerID
    
    
def config_check():
    """ Verify that config is set. """
    cfg = config["General"]["prefix"]
    if cfg == "None":
        raise Exception("Discord command prefix is not set.")
    
    cfg = config["Discord"]["discordToken"]
    if cfg == "None":
        raise Exception("Discord token is not set.")

    cfg = config["Discord"]["discordTextChannelId"]
    if cfg == "None":
        raise Exception("Discord text channel id is not set.")

    cfg = config["Battlemetrics"]["battlemetricsToken"]
    if cfg == "None":
        raise Exception("Battlemetrics token is not set.")

    cfg = config["Battlemetrics"]["banListId"]
    if cfg == "None":
        raise Exception("Battlemetrics banlist id is not set.")
    
    cfg = config["Battlemetrics"]["pollingInterval"]
    if cfg == "None":
        raise Exception("Battlemetrics polling interval is not set.")





if __name__ == "__main__":
    config_check()
    bot = BMQueryBot()
    bot.run(DC_TOKEN)