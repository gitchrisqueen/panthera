import React, { useEffect, useState } from 'react';
import { fetchUsers } from '../services/api';
import '../styles/UserList.css';

function UserList() {
    const [users, setUsers] = useState([]);

    useEffect(() => {
        fetchUsers().then(data => setUsers(data));
    }, []);

    return (
        <div className="UserList">
            <h2>Users</h2>
            <ul>
                {users.map(user => (
                    <li key={user.id}>{user.username}</li>
                ))}
            </ul>
        </div>
    );
}

export default UserList;