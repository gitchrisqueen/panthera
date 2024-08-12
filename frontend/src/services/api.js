// TODO: Add error handling for API calls. [Milestone: Error Handling]

const API_URL = 'http://localhost:5000';

export async function fetchUsers() {
    const response = await fetch(`${API_URL}/users`);
    return response.json();
}

export async function fetchGames() {
    const response = await fetch(`${API_URL}/games`);
    return response.json();
}

export async function fetchBettingLines() {
    const response = await fetch(`${API_URL}/betting_lines`);
    return response.json();
}

export async function fetchAlerts() {
    const response = await fetch(`${API_URL}/alerts`);
    return response.json();
}