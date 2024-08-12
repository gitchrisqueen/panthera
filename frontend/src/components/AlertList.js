// TODO: Add alert interaction features. [Milestone: Alert Features]

import React, { useEffect, useState } from 'react';
import { fetchAlerts } from '../services/api';
import '../styles/AlertList.css';

function AlertList() {
    const [alerts, setAlerts] = useState([]);

    useEffect(() => {
        fetchAlerts().then(data => setAlerts(data));
    }, []);

    return (
        <div className="AlertList">
            <h2>Alerts</h2>
            <ul>
                {alerts.map(alert => (
                    <li key={alert.id}>{alert.condition}</li>
                ))}
            </ul>
        </div>
    );
}

export default AlertList;