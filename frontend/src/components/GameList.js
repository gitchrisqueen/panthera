import React, { useEffect, useState } from 'react';
import { fetchGames } from '../services/api';
import '../styles/GameList.css';

function GameList() {
    const [games, setGames] = useState([]);

    useEffect(() => {
        fetchGames().then(data => setGames(data));
    }, []);

    return (
        <div className="GameList">
            <h2>Games</h2>
            <ul>
                {games.map(game => (
                    <li key={game.id}>{game.team_home} vs {game.team_away}</li>
                ))}
            </ul>
        </div>
    );
}

export default GameList;