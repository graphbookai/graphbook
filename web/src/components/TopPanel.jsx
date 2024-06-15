

import React, { useCallback, useEffect, useState } from 'react';
import { Popover, Input, Modal } from 'antd';
import { LinkOutlined, DisconnectOutlined, SettingFilled } from '@ant-design/icons';
import Settings from './Settings';
import { useSettings } from '../hooks/Settings';
import { API } from '../api';
import './top-panel.css';

const iconStyle = { fontSize: '18px', margin: '0 5px', lineHeight: '40px', height: '100%'};
const connectedStyle = {...iconStyle, color: 'green'};
const disconnectedStyle = {...iconStyle, color: 'red'};

export default function TopPanel() {
    const title = 'Graphbook';
    const [settings, setSetting] = useSettings();
    const [connected, setConnected] = useState(false);
    const [host, setHost] = useState(settings.graphServerHost);
    const [hostEditorOpen, setHostEditorOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);

    useEffect(() => {
        const handleOpen = () => setConnected(true);
        const handleClose = () => setConnected(false);
        API.addWsEventListener('open', handleOpen);
        API.addWsEventListener('close', handleClose);
        return () => {
            API.removeWsEventListener('open', handleOpen);
            API.removeWsEventListener('close', handleClose);
        };
    }, []);

    const setAPIHost = useCallback(host => {
        setSetting("graphServerHost", host);
    });

    const onHostChange = useCallback((e) => {
        setHost(e.target.value);
    }, [host]);

    const onOpenChange = useCallback(isOpen => {
        setHostEditorOpen(isOpen);
        if (!isOpen && host !== API.getHost()) {
            setAPIHost(host);
        }
    }, [host]);

    const closeAndUpdateHost = useCallback(() => {
        setHostEditorOpen(false);
        setAPIHost(host);
    });

    const setSettingsModal = useCallback((shouldOpen) => {
        setSettingsOpen(shouldOpen);
    });


    const hostEditor = (
        <Input
            onChange={onHostChange}
            onPressEnter={closeAndUpdateHost}
            addonBefore="http://"
            defaultValue={host}
            trigger="hover"/>
    );
    
    return (
        <div className="top-panel">
            <div className="textual">
                <h2 className="title">{title}</h2>
                <div style={iconStyle}>
                    <SettingFilled style={iconStyle} onClick={() => setSettingsModal(true)}/>
                    <Popover content={hostEditor} title="Host" placement="leftTop" onOpenChange={onOpenChange} open={hostEditorOpen}>
                        {connected ? <LinkOutlined style={connectedStyle}/> : <DisconnectOutlined style={disconnectedStyle}/>}
                    </Popover>
                </div>
            </div>

            <Modal width={1000} title="Settings" open={settingsOpen} onCancel={() => setSettingsModal(false)} footer={null}>
                <Settings/>
            </Modal>
        </div>
    )
}