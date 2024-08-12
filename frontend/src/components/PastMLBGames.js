/*
 * Copyright (c) 2024. Christopher Queen Consulting LLC (http://www.ChristopherQueenConsulting.com/)
 */

// frontend/src/components/PastMLBGames.js

import React, { useEffect, useState } from 'react';

const PastMLBGames = () => {
  const [games, setGames] = useState([]);

  useEffect(() => {
    fetch('/api/past-mlb-games')
      .then(response => response.json())
      .then(data => setGames(data))
      .catch(error => console.error('Error fetching past MLB games:', error));
  }, []);

  return (
    <div>
      <h2>Past MLB Games</h2>
      <ul>
        {games.map(game => (
          <li key={game.id}>
            {game.date} - {game.team1} vs {game.team2}: {game.score1} - {game.score2}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default PastMLBGames;