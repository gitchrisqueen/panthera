// TODO: Add routing and state management. [Milestone: MVP]

import React from 'react';
import Header from './components/Header';
import Footer from './components/Footer';
import UserList from './components/UserList';
import GameList from './components/GameList';
import BettingLineList from './components/BettingLineList';
import AlertList from './components/AlertList';
import './styles/App.css';

function App() {
    return (
        <div className="App">
            <Header />
            <main>
                <UserList />
                <GameList />
                <BettingLineList />
                <AlertList />
                 <PastMLBGames />
            </main>
            <Footer />
        </div>
    );
}

export default App;