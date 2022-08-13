# import packages to allow regex handling of url subdirectories

import re
import urllib
import urllib.request
from time import sleep

# import beautifulsoup library to help parse the tables where player information is stored
from bs4 import BeautifulSoup, Tag

# create an instance of the beautifulsoup class to parse the page
f = urllib.request.urlopen('http://www.espn.com/nba/teams')
teams_soup = BeautifulSoup(f.read(), 'html.parser')

# define an iterable helper class to pull list of links using regexes
class my_regex_searcher:
    def __init__(self, regex_string):
        self.__r = re.compile(regex_string)
        self.groups = []

    def __call__(self, what):
        if isinstance(what, Tag):
            what = what.name

        if what:
            g = self.__r.findall(what)
            if g:
                self.groups.append(g)
                return True
        return False

    def __iter__(self):
        yield from self.groups

# create instance of regex_searcher for links to roster pages
roster_searcher = my_regex_searcher(r"/nba/team/roster/_/name/(\w+)/(.+)")

# add all roster page links to a dictionary to unpack the regex searcher object
scraped_roster_details = dict(zip(teams_soup.find_all(href=roster_searcher), roster_searcher))

# extract the components of the keys and values in this intermediate dictionary
# and re-zip them together to create the final cleaned dictionary we'll want to use
teams = []
links = []

for value in scraped_roster_details.values():
    teams.append(value[0][1])

for key in scraped_roster_details.keys():
    links.append('https://www.espn.com' + key.get('href'))    

rosters_library = dict(zip(teams,links))

# display the dictionary keys
rosters_library.keys()

# create function to take a team roster url and collect all player info

def get_player_info(team_roster_url):
    f = urllib.request.urlopen(team_roster_url)
    team_roster_soup = BeautifulSoup(f.read(), 'html.parser')
    
    # Part 1: Create table headers
    table_headers = team_roster_soup.find_all('th', {'class':'Table__TH'})

    # convert bs4 result set into string array for regex matching
    header_values = []
    for x in table_headers:
        header_values.append(str(x))

    # extract list of table headers
    column_names = []
    for x in header_values:

        # Append conditionally to avoid blank spacer block at the top left of the tables
        if len(re.findall(">([a-zA-Z]+?)<",header_values[header_values.index(x)])) > 0:
            column_names.append(re.findall(">([a-zA-Z]+?)<",header_values[header_values.index(x)])[0])
    
    # Part 2: Create player dictionaries
    roster_dict = dict()

    # Loop through indexes 0-30, which will cover the largest roster size of any NBA team.
    for i in range(0,30):

        # parse corresponding row of table
        player = team_roster_soup.find_all('tr', {'data-idx': i})

        # extract all key values from columns

        # convert bs4 result set into string array for regex matching
        p_values = []
        for x in player:
            p_values.append(str(x))

        # match to contents of tags
        try:
            player_stats = re.findall("<.+?\">([a-zA-Z0-9$;,\'\"\s\.\-\&]{1,25}?)</(?!span)", p_values[0])
            player_dict = dict(zip(column_names, player_stats))
            roster_dict[player_dict['Name']] = player_dict
        except IndexError:
            pass

    return roster_dict

# create master dictionary of teams and player info
all_players = dict()

for team in rosters_library.keys():
    all_players[team] = get_player_info(rosters_library[team])

# import pandas library
import pandas as pd

# initialize empty pandas dataframe
all_players_df = pd.DataFrame()

# loop through each team, creating a pandas dataframe as described above
# and append the records to the all_players_df object
# adding an extra field 'team' to keep track of data sources

for team in all_players:
    roster_df = pd.DataFrame.from_dict(all_players[team], orient = 'index')
    roster_df['Team'] = team
    all_players_df = pd.concat([all_players_df, roster_df])

# create a function to take a team roster url and collect all of the player ids

def get_player_ids(team_roster_url):
    f = urllib.request.urlopen(team_roster_url)
    team_roster_soup = BeautifulSoup(f.read(), 'html.parser')

    # create player id dictionaries
    ids_dict = dict()

    # Loop through indexes 0-30, which will cover the largest roster size of any NBA team.
    for i in range(0,30):

        # parse corresponding row of table
        player_id = team_roster_soup.find_all('tr', {'data-idx': i})

        # extract all ids from anchor links

        # convert bs4 result set into string array for regex matching
        id_values = []
        for x in player_id:
            id_values.append(str(x))

        # match to contents of tags
        try:
            player_name = re.findall("<.+?\">([a-zA-Z0-9$;,\'\"\s\.\-\&]{1,25}?)</(?!span)", id_values[0])[0]
            player_id = re.findall("href=\"https://www.espn.com/nba/player/_/id/(\d+?)/[\w\-]+?\"", id_values[0])[0]
            player_url = re.findall("href=\"(https://www.espn.com/nba/player/_/id/\d+?/[\w\-]+?)\"", id_values[0])[0]
            ids_dict[player_name] = dict({'id': player_id, 'url': player_url})
        except IndexError:
            pass

    return ids_dict

# create a new dictionary to hold all player ids

all_player_ids = dict()

# populate this new dictionary with the ids of all players across every NBA team

for team in rosters_library.keys():
    all_player_ids[team] = get_player_ids(rosters_library[team])

# initialize empty pandas dataframe for ids
all_player_ids_df = pd.DataFrame()

# loop through each team, creating a pandas dataframe
# and append the records to the all_player_ids_df object

for team in all_player_ids:
    roster_ids_df = pd.DataFrame.from_dict(all_player_ids[team], orient = 'index')
    all_player_ids_df = pd.concat([all_player_ids_df, roster_ids_df])

# update the all_players_df object with ids

# note: there are no two players currently in the NBA with the exact same first and last name,
# and it is unlikely there will be in the future. If this situation did occur, we would need to use
# the pandas.merge function and specify the name column AND another identifying column (e.g., team)
# rather than simply joining on the indexes, which in this case are also the names of the players
all_players_df = all_players_df.join(all_player_ids_df)

# create a function that takes a player page url and scrapes a players stats, adding them to a dictionary

def get_player_stats(player_url):
    # parse individual player's page
    f = urllib.request.urlopen(player_url)
    player_soup = BeautifulSoup(f.read(), 'html.parser')

    # would return blank a blank bs4 ResultSet object if the player stats card did not exist
    player_stats = player_soup.find_all('section', {'class':'Card PlayerStats'})

    # convert the bs4 resultSet to a string
    try:
        player_stat_card = str(player_stats[0])
    except IndexError:
        player_stat_card = []

    # search the card for career stats record
    try:
        row_number = re.findall("data-idx=\"(\d)\"><td class=\"Table__TD\">Career</td>",player_stat_card)[0]
    except TypeError:
        pass

    # pull the list of column headers
    try:
        card_headers = re.findall("class=\"Table__TH\".+?>(.+?)</th>", player_stat_card)
    except TypeError:
        pass

    # pull the list of career stats
    try:
        player_career_stats = re.findall("data-idx=\"{row_number}\">(.+?)</tr>".format(row_number = row_number), player_stat_card)
    except (TypeError, UnboundLocalError) :
        pass

    # convert from bs4 resultSet to list
    try:
        card_data = []
        for x in player_career_stats:
            stats = re.findall("<td class=\"Table__TD\">(.+?)</td>",player_career_stats[player_career_stats.index(x)])
            for y in stats:
                card_data.append(str(y))
    except (IndexError, TypeError, UnboundLocalError):
        pass

    try:
        player_dict = dict(zip(card_headers, card_data))
    except (TypeError, UnboundLocalError):
        pass

    try:
        return player_dict
    except:
        player_dict = dict()
        return player_dict

# create a function that takes a dataframe with player names as indexes and uses the above stats-
# scraping function to return a dictionary of all player career avg. stats for an entire NBA team

def compile_all_stats(players_dataframe):

    career_stats_dict = dict()

    for player, info in players_dataframe.iterrows():
        player_url = players_dataframe.loc[player]["url"]
        pstats_dict = get_player_stats(player_url)
        career_stats_dict[player] = pstats_dict
    
    return career_stats_dict

# compile player career stats dictionary by scraping every NBA player's page
player_stats_dict = compile_all_stats(all_players_df)

# create final dataframe to join with existing player-level data
all_player_stats_df = pd.DataFrame.from_dict(player_stats_dict, orient = 'index')

# join the all_players_df and all_player_stats_df objects
all_players_df = all_players_df.join(all_player_stats_df)

# convert empty salaries to 0s
all_players_df['Salary'] = [re.sub(r'--', '$0', x) if isinstance(x, str) else x for x in all_players_df['Salary'].values]

# convert salaries to numerical values using list comprehension
all_players_df['Salary'] = [int(re.sub(r'[^\d]+', '', x)) if isinstance(x, str) else x for x in all_players_df['Salary'].values]

# convert empty ages to 0s
all_players_df['Age'] = [re.sub(r'--', '0', x) if isinstance(x, str) else x for x in all_players_df['Age'].values]

# convert ages to numerical values using list comprehension
all_players_df['Age'] = [int(x) if isinstance(x, str) else x for x in all_players_df['Age'].values]

# define a function that takes a string in ft' in" format and converts to total inches as a numerical value

def convert_height(height):
    height_splits = height.split()
    feet = float(height_splits[0].replace("\'",""))
    inches = float(height_splits[1].replace("\"",""))
    return (12*feet + inches)

# convert heights to numerical values using list comprehension

all_players_df['HT'] = [float(convert_height(x)) if isinstance(x, str) else x for x in all_players_df['HT'].values]

# next, convert weights to numerical values with list comprehension

all_players_df['WT'] = [float(x.split(" ")[0]) if isinstance(x, str) else x for x in all_players_df['WT'].values]

# define dictionary of desired columns and types
stat_types = {
    'GP': 'float64',
    'MIN': 'float64',
    'FG%': 'float64',
    '3P%': 'float64',
    'FT%': 'float64',
    'REB': 'float64',
    'AST': 'float64',
    'BLK': 'float64',
    'STL': 'float64',
    'PF': 'float64',
    'TO': 'float64',
    'PTS': 'float64'
}

# convert all stats columns to floats using the above dictionary (in-place)
all_players_df = all_players_df.astype(dtype=stat_types, copy=False, errors='raise')

# export cleaned dataset as csv
all_players_df.to_csv('Aug_2022_NBA_players_full_dataset_cleaned_from_script.csv')

# read in the dataset to dataframe from a csv
# your_df = pd.read_csv('Aug_2022_NBA_players_full_dataset_cleaned.csv', index_col=0)