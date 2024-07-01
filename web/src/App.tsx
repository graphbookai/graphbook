import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Flow from './components/Flow';
import TopPanel from './components/TopPanel'
import { Layout, ConfigProvider, theme } from 'antd';
import LeftPanel from './components/LeftPanel/LeftPanel';
import { useSettings } from './hooks/Settings';
import { API } from './api';
import { useAPI } from './hooks/API';

const { Header, Content, Sider } = Layout;

import 'reactflow/dist/style.css';
import './components/Nodes/node.css';

import { CodeEditor } from './components/Editor/CodeEditor';

export default function App() {
    const [settings, _] = useSettings();
    useAPI();
    const themeAlgorithm = settings.theme === "Light" ? theme.defaultAlgorithm : theme.darkAlgorithm;

    useEffect(() => {
        API.connect(settings.graphServerHost, settings.mediaServerHost);
        return () => {
            API.disconnect();
        };
    }, []);

    useEffect(() => {
        if (API.getHost() !== settings.graphServerHost) {
            API.setHost(settings.graphServerHost);
        }
        if (API.getMediaHost() !== settings.mediaServerHost) {
            API.setMediaHost(settings.mediaServerHost);
        }

    }, [settings]);

    return (
        <ConfigProvider theme={{ algorithm: themeAlgorithm }}>
            <View/>
        </ConfigProvider>
    );
}

function View() {
    const {
        token: { colorBgContainer, colorBorder },
    } = theme.useToken();
    const [codeEditor, setCodeEditor] = useState<{name: string} | null>(null);
    const [worflowFile, setWorkflowFile] = useState<string | null>(null);
    
    const onBeginEdit = useCallback((val) => {
        setCodeEditor(val);
    }, []);

    const codeEditorView = useMemo(() => {
        if (codeEditor) {
            return <CodeEditor name={codeEditor.name} closeEditor={()=>setCodeEditor(null)} />;
        }
        return <></>

    }, [codeEditor]);

    return (
        <Layout style={{ height: '100vh' }}>
            <Header style={{ height: '40px', background: colorBgContainer, borderBottom: `1px solid ${colorBorder}` }}>
                <TopPanel/>
            </Header>
            <Content style={{ height: '100%' }}>
                <Layout style={{ width: '100vw', height: '100%' }}>
                    <Sider width={300} style={{ background: colorBgContainer }}>
                        <LeftPanel setWorkflow={setWorkflowFile} onBeginEdit={onBeginEdit} />
                    </Sider>
                    {codeEditorView}
                    <Flow filename={worflowFile} />
                </Layout>
            </Content>
        </Layout>
    );
}
