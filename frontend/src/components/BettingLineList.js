// TODO: Add betting line interaction features. [Milestone: Betting Features]

import React, { useEffect, useState } from 'react';
import { fetchBettingLines } from '../services/api';
import '../styles/BettingLineList.css';

function BettingLineList() {
    const [lines, setLines] = useState([]);

    useEffect(() => {
        fetchBettingLines().then(data => setLines(data));
    }, []);

    return (
        <div className="BettingLineList">
            <h2>Betting Lines</h2>
            <ul>
                {lines.map(line => (
                    <li key={line.id}>{line.line}</li>
                ))}
            </ul>
        </div>
    );
}

export default BettingLineList;