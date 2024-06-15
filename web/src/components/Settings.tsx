import { useEffect, useState, useCallback } from 'react';
import { Switch, Input, Typography, Flex, theme, Button, Space } from 'antd';
import { API } from '../api';
import { useSettings } from '../hooks/Settings';
import React from 'react';

const { Text, Title } = Typography;

export default function Settings() {
    const [mediaSettings, setMediaSettings] = useState({root_path: ''});
    const [clientSettings, setClientSetting] = useSettings();

    useEffect(() => {
        const fetchMediaSettings = async () => {
            const response = await API.getMediaServerVars();
            if (response) {
                setMediaSettings(response);
            }
        };
        fetchMediaSettings();
    }, []);

    const setMediaVar = useCallback(async (name, value) => {
        setMediaSettings({...mediaSettings, [name]: value});
        await API.setMediaServerVar('root_path', mediaSettings.root_path);
    }, [mediaSettings]);

    const setGraphServerHost = useCallback((value) => {
        setClientSetting('graphServerHost', value);
    }, []);

    const setMediaServerHost = useCallback((value) => {
        setClientSetting('mediaServerHost', value);
    }, []);

    return (
        <div style={{height: '60vh'}}>
            <Title level={4}>Client Settings</Title>
            <SettingsEntrySwitch
                name="Theme"
                checked={clientSettings.theme === "Dark"}
                checkedText="Dark"
                uncheckedText="Light"
                onChange={(checked) => {setClientSetting('theme', checked ? "Dark" : "Light")}}
            />
            <SettingsEntryInput name="Graph Server Host" value={clientSettings.graphServerHost} addonBefore="http://" onApply={setGraphServerHost}/>
            <SettingsEntryInput name="Media Server Host" value={clientSettings.mediaServerHost} addonBefore="http://" onApply={setMediaServerHost}/>
            <Title level={4}>Server Settings</Title>
            <SettingsEntryInput name="Media Root Path" value={mediaSettings.root_path} onChange={(value)=>setMediaVar('root_path', value)}/>
            
        </div>
    );
}

function SettingsEntryInput({name, value, ...optionalProps}) {
    const { onChange, onApply, addonBefore } = optionalProps;
    const [inputValue, setInputValue] = useState(value);

    const onChangeSetting = useCallback((value) => {
        setInputValue(value);
        if (onChange) {
            onChange(value);
        }
    }, []);

    const onPressEnter = onApply ? () => onApply(inputValue) : () => {};

    return (
        <Flex vertical>
            <Text>{name}</Text>
            <Flex vertical={false}>
                <Space>
                    <Input value={inputValue} onChange={(e)=>onChangeSetting(e.target.value)} addonBefore={addonBefore} onPressEnter={onPressEnter}/>
                    { onApply && <Button onClick={()=>onApply(inputValue)}>Apply</Button> }
                </Space>
            </Flex>
        </Flex>
    );
}

function SettingsEntrySwitch({name, checked, checkedText, uncheckedText, onChange}) {
    return (
        <Flex vertical>
            <Text>{name}</Text>
            <Flex vertical={false}>
            <Switch
                checked={checked}
                checkedChildren={checkedText}
                unCheckedChildren={uncheckedText}
                onChange={onChange}
            />
            </Flex>
        </Flex>
    );
}
