import { useEffect, useState, useCallback, useMemo } from 'react';
import { Switch, Input, Typography, Flex, Button, Space, Checkbox, Slider, Radio } from 'antd';
import { API } from '../api';
import { useSettings } from '../hooks/Settings';
import React from 'react';

const { Text, Title } = Typography;
const NODE_TABS_OPTIONS = {
    "ICONS": "Icons Only",
    "NAMES": "Names Only",
    "BOTH": "Both"
};

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

    const setImageHeight = useCallback((value) => {
        setClientSetting('quickviewImageHeight', value);
    }, []);

    const disableTooltips = useCallback((event) => {
        setClientSetting('disableTooltips', event.target.checked);
    }, []);

    const setNodeTabsDisplay = useCallback((value) => {
        setClientSetting('nodeTabsDisplay', value);
    }, []);

    return (
        <div style={{ height: '60vh', overflow: 'auto' }}>
            <Space direction='vertical' style={{ width: '100%' }}>
                <Title level={4}>Client Settings</Title>
                <SettingsEntrySwitch
                    name="Theme"
                    checked={clientSettings.theme === "Dark"}
                    checkedText="Dark"
                    uncheckedText="Light"
                    onChange={(checked) => { setClientSetting('theme', checked ? "Dark" : "Light") }}
                />
                <SettingsEntryRadioGroup
                    name="Node Tabs Display"
                    options={NODE_TABS_OPTIONS}
                    value={clientSettings.nodeTabsDisplay}
                    onChange={setNodeTabsDisplay}
                />
                <Checkbox onChange={disableTooltips} checked={clientSettings.disableTooltips}>Disable Tooltips <Text type="secondary">(improves UI performance)</Text></Checkbox>
                <SettingsEntryInput name="Graph Server Host" value={clientSettings.graphServerHost} addonBefore="http://" onApply={setGraphServerHost} />

                <Title level={4}>Media Server Settings</Title>
                <Checkbox onChange={setUseExternalMediaServer} checked={clientSettings.useExternalMediaServer}>Use External Media Server</Checkbox>
                <SettingsEntryInput name="Media Server Host" value={clientSettings.mediaServerHost} addonBefore="http://" onApply={setMediaServerHost} disabled={!clientSettings.useExternalMediaServer} />
                <SettingsEntryInput name="Media Root Path" value={mediaSettings.root_path} onChange={(value) => setMediaVar('root_path', value)} disabled={!clientSettings.useExternalMediaServer} />

                <Title level={4}>Quickview Settings</Title>
                <Flex vertical>
                    <Text>Image Height</Text>
                    <Slider
                        style={{ maxWidth: '50%', marginLeft: 10 }}
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

function SettingsEntryRadioGroup({ name, options, value, onChange }) {
    const groupOptions = useMemo(() => Object.entries<string>(options).map(([key, value]) => ({
        label: value,
        value: key
    })), [options]);

    const onValueChange = useCallback((e) => {
        onChange(e.target.value);
    }, [onChange]);

    return (
        <Flex vertical>
            <Text>{name}</Text>
            <Radio.Group
                block
                optionType="button"
                options={groupOptions}
                value={value}
                onChange={onValueChange}
            />
        </Flex>
    );
}
