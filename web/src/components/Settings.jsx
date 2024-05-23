import { useState } from 'react';
import { Switch, theme } from 'antd';

export default function Settings({setAppSettings}) {
    const [settings, setSettings] = useState({
        themeAlgorithmSerialized: "Light",
    });

    return (
        <div style={{height: '60vh'}}>
            <Switch
                checked={settings.themeAlgorithmSerialized === "Dark"}
                checkedChildren="Dark"
                unCheckedChildren="Light"
                onChange={(checked) => {
                    setSettings({
                        ...settings,
                        themeAlgorithmSerialized: checked ? "Dark" : "Light"
                    });
                    setAppSettings({
                        ...settings,
                        themeAlgorithm: checked ? theme.darkAlgorithm : theme.lightAlgorithm
                    });
                }}
            />
            
        </div>
    );
}
