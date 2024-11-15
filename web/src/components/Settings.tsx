import { useEffect, useState, useCallback } from 'react';
import { Switch, Input, Typography, Flex, theme, Button, Space, Checkbox, Slider } from 'antd';
import { API } from '../api';
import { useSettings } from '../hooks/Settings';
import React from 'react';

const { Text, Title } = Typography;

export default function Settings() {
    const [mediaSettings, setMediaSettings] = useState({ root_path: '' });
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

    const setMediaVar = useCallback((name, value) => {
        setMediaSettings({ ...mediaSettings, [name]: value });
        API.setMediaServerVar(name, value);
    }, [mediaSettings]);

    const setGraphServerHost = useCallback((value) => {
        setClientSetting('graphServerHost', value);
    }, []);

    const setUseExternalMediaServer = useCallback((event) => {
        setClientSetting('useExternalMediaServer', event.target.checked);
    }, []);

    const setMediaServerHost = useCallback((value) => {
        setClientSetting('mediaServerHost', value);
    }, []);

    const setShowNotes = useCallback((event) => {
        setClientSetting('quickviewShowNotes', event.target.checked);
    }, []);

    const setShowImages = useCallback((event) => {
        setClientSetting('quickviewShowImages', event.target.checked);
    }, []);


    const setImageHeight = useCallback((value) => {
        setClientSetting('quickviewImageHeight', value);
    }, []);

    const disableTooltips = useCallback((event) => {
        setClientSetting('disableTooltips', event.target.checked);
    }, []);


    return (
        <div style={{ height: '60vh', overflow: 'auto' }}>
            <Space direction='vertical'>
                <Title level={4}>Client Settings</Title>
                <SettingsEntrySwitch
                    name="Theme"
                    checked={clientSettings.theme === "Dark"}
                    checkedText="Dark"
                    uncheckedText="Light"
                    onChange={(checked) => { setClientSetting('theme', checked ? "Dark" : "Light") }}
                />
                <Checkbox onChange={disableTooltips} checked={clientSettings.disableTooltips}>Disable Tooltips <Text type="secondary">(improves UI performance)</Text></Checkbox>
                <SettingsEntryInput name="Graph Server Host" value={clientSettings.graphServerHost} addonBefore="http://" onApply={setGraphServerHost} />

                <Title level={4}>Media Server Settings</Title>
                <Checkbox onChange={setUseExternalMediaServer} checked={clientSettings.useExternalMediaServer}>Use External Media Server</Checkbox>
                <SettingsEntryInput name="Media Server Host" value={clientSettings.mediaServerHost} addonBefore="http://" onApply={setMediaServerHost} disabled={!clientSettings.useExternalMediaServer} />
                <SettingsEntryInput name="Media Root Path" value={mediaSettings.root_path} onChange={(value) => setMediaVar('root_path', value)} disabled={!clientSettings.useExternalMediaServer} />

                <Title level={4}>Quickview Settings</Title>
                <Checkbox onChange={setShowNotes} checked={clientSettings.quickviewShowNotes}>Show Notes</Checkbox>
                <Checkbox onChange={setShowImages} checked={clientSettings.quickviewShowImages}>Show Images</Checkbox>
                <Flex vertical>
                    <Text>Image Height</Text>
                    <Slider
                        min={50}
                        max={200}
                        defaultValue={100}
                        value={clientSettings.quickviewImageHeight}
                        onChange={setImageHeight}
                    />
                </Flex>
            </Space>
        </div>
    );
}

function SettingsEntryInput({ name, value, ...optionalProps }) {
    const { onChange, onApply, addonBefore, disabled } = optionalProps;
    const [inputValue, setInputValue] = useState(value);

    const onChangeSetting = useCallback((value) => {
        setInputValue(value);
        if (onChange) {
            onChange(value);
        }
    }, []);

    const onPressEnter = onApply ? () => onApply(inputValue) : () => { };

    return (
        <Flex vertical>
            <Text>{name}</Text>
            <Flex vertical={false}>
                <Space>
                    <Input value={inputValue} onChange={(e) => onChangeSetting(e.target.value)} addonBefore={addonBefore} onPressEnter={onPressEnter} disabled={disabled} />
                    {onApply && <Button onClick={() => onApply(inputValue)}>Apply</Button>}
                </Space>
            </Flex>
        </Flex>
    );
}

function SettingsEntrySwitch({ name, checked, checkedText, uncheckedText, onChange }) {
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
