import React, { useState } from "react";

export function ExamplePanel({ useAPIMessage }) {
    const [util, setUtil] = useState({});
    useAPIMessage("system_util", (data) => {
        setUtil(data);
    });

    return (
        <div style={{width: '100%', overflow: 'auto'}}>
            <h1>System Utilization</h1>
            <pre>{JSON.stringify(util, null, 2)}</pre>
        </div>
    );
}
