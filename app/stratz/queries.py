PLAYER_BUNDLE_QUERY = """
query PlayerBundle($steamAccountId: Long!, $take: Int!) {
  player(steamAccountId: $steamAccountId) {
    steamAccount {
      id
      name
      avatar
      seasonRank
      seasonLeaderboardRank
    }
    matches(request: { take: $take }) {
      id
      startDateTime
      durationSeconds
      gameMode
      lobbyType
      didRadiantWin
      players {
        steamAccountId
        heroId
        playerSlot
        isRadiant
        isVictory
        kills
        deaths
        assists
        goldPerMinute
        experiencePerMinute
        heroDamage
        towerDamage
        heroHealing
        numLastHits
        lane
        role
        position
      }
    }
  }
}
"""

PLAYER_STYLE_BUNDLE_QUERY = """
query PlayerStyleBundle($steamAccountId: Long!, $take: Int!) {
  player(steamAccountId: $steamAccountId) {
    matches(request: { take: $take }) {
      id
      startDateTime
      durationSeconds
      gameMode
      lobbyType
      didRadiantWin
      players {
        steamAccountId
        heroId
        playerSlot
        isRadiant
        isVictory
        kills
        deaths
        assists
        goldPerMinute
        experiencePerMinute
        heroDamage
        towerDamage
        heroHealing
        numLastHits
        lane
        role
        position
        item0Id
        item1Id
        item2Id
        item3Id
        item4Id
        item5Id
        backpack0Id
        backpack1Id
        backpack2Id
        neutral0Id
        abilities {
          abilityId
          time
          level
          isTalent
        }
      }
    }
  }
}
"""

MATCH_DETAILS_QUERY = """
query MatchDetails($matchId: Long!) {
  match(id: $matchId) {
    id
    startDateTime
    durationSeconds
    gameMode
    lobbyType
    didRadiantWin
    players {
      steamAccountId
      heroId
      playerSlot
      isRadiant
      isVictory
      kills
      deaths
      assists
      goldPerMinute
      experiencePerMinute
      heroDamage
      towerDamage
      heroHealing
      numLastHits
      lane
      role
      position
      item0Id
      item1Id
      item2Id
      item3Id
      item4Id
      item5Id
      backpack0Id
      backpack1Id
      backpack2Id
      neutral0Id
      abilities {
        abilityId
        time
        level
        isTalent
      }
    }
  }
}
"""

HERO_CONSTANTS_QUERY = """
query HeroConstants {
  constants {
    heroes {
      id
      name
      shortName
      displayName
      roles {
        roleId
        level
      }
      language {
        displayName
      }
    }
  }
}
"""

HERO_GLOBAL_STATS_QUERY = """
query HeroGlobalStats {
  heroStats {
    stats {
      heroId
      matchCount
      winCount
    }
  }
  constants {
    heroes {
      id
      name
      shortName
      displayName
      roles {
        roleId
        level
      }
      language {
        displayName
      }
    }
  }
}
"""

HERO_BUILDS_QUERY = """
query HeroBuilds($heroId: Short!, $matchLimit: Int!) {
  heroStats {
    itemFullPurchase(heroId: $heroId, matchLimit: $matchLimit) {
      heroId
      itemId
      time
      matchCount
      winCount
      winsAverage
    }
    itemStartingPurchase(heroId: $heroId) {
      heroId
      itemId
      wasGiven
      matchCount
      winCount
      winsAverage
    }
    itemBootPurchase(heroId: $heroId) {
      heroId
      itemId
      timeAverage
      matchCount
      winCount
      winAverage
    }
    itemNeutral(heroId: $heroId) {
      heroId
      itemId
      matchCount
      winCount
      equippedMatchCount
      equippedMatchWinCount
    }
    talent(heroId: $heroId) {
      heroId
      abilityId
      timeAverage
      matchCount
      winCount
      winsAverage
    }
    abilityMinLevel(heroId: $heroId) {
      heroId
      abilityId
      level
      matchCount
      winCount
    }
    abilityMaxLevel(heroId: $heroId) {
      heroId
      abilityId
      level
      matchCount
      winCount
    }
    guide(heroId: $heroId, take: 5) {
      heroId
      matchCount
      guides {
        matchId
        createdDateTime
        itemIds
        neutralItemIds
      }
    }
  }
  constants {
    heroes {
      id
      name
      shortName
      displayName
      language {
        displayName
      }
    }
    items {
      id
      name
      displayName
      shortName
      language {
        displayName
      }
    }
    abilities {
      id
      name
      language {
        displayName
      }
    }
  }
}
"""
