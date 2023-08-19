import pandas as pd
from scipy.spatial.distance import cosine
import json
import numpy as np
from collections import Counter
import datetime 
import requests
import ast

from flask import Flask
from flask import request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def getData():
    # get teams from past week
    today = datetime.datetime.today()
    data = {"teams": []}
    url = "https://api.statsugiri.gg/teams/gen9ou/"

    for i in range(1, 14): # two week's worth of teams
        day = str(today -  datetime.timedelta(days=i))
        day = day.split(" ")[0] # get only the year month day portion of day
        response = requests.get(url + day)

        if response.ok:
            content = json.loads(response.content)
            data["teams"].extend(content["teams"])
    return data


def getPokemon(data):
    # get a set of all pokemon used in the dataset
    pokemon = set()
    for team in data["teams"]:
        pokemon.update(set(team['pkmn_team']))
    
    print("There are " + str(len(pokemon))  + " found")
    return sorted(pokemon)

def getDataframe(data, pokemon):
    teams = [team["pkmn_team"] for team in data["teams"]]
    rows = []

    for team in teams:
        row = [0 for mon in pokemon]
        for member in team:
            # add a 1 to the df[row][col]
            colIndex = pokemon.index(member)
            row[colIndex] = 1

        rows.append(row)

    df = pd.DataFrame(columns=pokemon, data=rows)
    return df

def getNeighbors(cardName, data):
    sortedNames = data.loc[cardName].sort_values(ascending=False).index[:10]
    return sortedNames

def getSimilarities(df):
    # Lets fill in those empty spaces with cosine similarities
    # Loop through the columns
    data_ibs = pd.DataFrame(index=df.columns, columns=df.columns)
    normalizer = 0.2

    for i in range(len(data_ibs.columns)):
        for j in range(len(data_ibs.columns)) :
            # Fill in placeholder with cosine similarities
            data_ibs.iloc[i,j] = 1-cosine(df.iloc[:,i],df.iloc[:,j]) + normalizer

    data_neighbours = pd.DataFrame(index=data_ibs.columns,columns=range(1,11))
    
    # Loop through our similarity dataframe and fill in neighbouring item names
    for i in range(0,len(data_ibs.columns)):
        cardName = data_ibs.columns[i]
        data_neighbours.iloc[i,:10] = getNeighbors(cardName, data_ibs)
    
    return (data_ibs, data_neighbours)

def getTeamRecommendations(data_ibs, team):
    if not team: return [["great tusk", 0]] # use great tusk as a default for teams with no pokemon in data_ibs
    neighbour_scores = Counter()
    #Loop through all columns (pokemon) and fill with similarity scores

    for pokemon in team:
        neighbour_top_sims = data_ibs.loc[pokemon].sort_values(ascending=False)[:10]

        for index, neighbour in enumerate(neighbour_top_sims):
            neighbour_species = neighbour_top_sims.index[index]
            similarity_sum = sum(data_ibs[pokemon]) # divide by total of all similarities

            if neighbour_species in team: continue # do not recommend mon to itself
            neighbour_scores[neighbour_species] += neighbour_top_sims[neighbour_species] / similarity_sum

    # Get the top pokemon recs
    result = sorted(neighbour_scores.items(), key=lambda x: x[1], reverse=True)
    return result[:6]

def processSpaces(data_ibs, team):
    processedTeam = []
    allPokemon = set(data_ibs.columns)

    for teamMember in team:
        if teamMember in allPokemon:
            processedTeam.append(teamMember)
        else:
            # replace dash with space
            noDashes = teamMember.replace("-", " ")
            if noDashes in allPokemon: 
                processedTeam.append(noDashes)
                continue

            # take out gendered forms of pokemon
            noMale = teamMember.replace("-male", "")
            noFemale = teamMember.replace("-female", "")
    
            if noMale in allPokemon: processedTeam.append(noMale)
            if noFemale in allPokemon: processedTeam.append(noFemale)
    
    return processedTeam

@app.route("/recommend", methods=['GET'])
def getRecommendation():
    team = request.args.get("team")
    team = ast.literal_eval(team) # converts the param string into a list
    team = processSpaces(data_ibs, team)
    recommendations = getTeamRecommendations(data_ibs, team)

    # cut out scores, which are recommendation[1] for recommendations
    print(recommendations)
    recommendations = [pokemon[0] for pokemon in recommendations]
    return {"recs": recommendations}

data = getData()
allPokemon = getPokemon(data)
df = getDataframe(data, allPokemon)
data_ibs, neighbours = getSimilarities(df)
