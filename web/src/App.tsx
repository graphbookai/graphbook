import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Flow from './components/Flow';
import TopPanel from './components/TopPanel'
import { Layout, ConfigProvider, theme } from 'antd';
import LeftPanel from './components/LeftPanel/LeftPanel';
import { useSettings } from './hooks/Settings';
import { API } from './api';
import { useAPI } from './hooks/API';
import { setGlobalFilename } from './hooks/Filename.ts';

const { Header, Content, Sider } = Layout;

import 'reactflow/dist/style.css';
import './components/Nodes/node.css';

import { CodeEditor } from './components/Editor/CodeEditor';
import { WelcomeScreen } from './components/WelcomeScreen';

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
            <View />
        </ConfigProvider>
    );
}

function View() {
    const {
        token: { colorBgContainer, colorBorder },
    } = theme.useToken();
    const [codeEditor, setCodeEditor] = useState<{ name: string } | null>(null);
    const [workflowFile, setWorkflowFile] = useState<string | null>(null);
    const API = useAPI();

    const onBeginEdit = useCallback((val) => {
        setCodeEditor(val);
    }, []);

    const codeEditorView = useMemo(() => {
        if (codeEditor) {
            return <CodeEditor name={codeEditor.name} closeEditor={() => setCodeEditor(null)} />;
        }
        return <></>

    }, [codeEditor]);

    const mainView = useMemo(() => {
        if (workflowFile) {
            return (
                <div style={{ width: '100%', height: '100%', position: 'relative' }}>
                    {codeEditorView}
                    <Flow filename={workflowFile} />
                </div>
            );
        }

        return <WelcomeScreen />;
    }, [workflowFile, codeEditorView, API]);

    const setFile = useCallback((filename: string) => {
        setWorkflowFile(filename);
        setGlobalFilename(filename);
    }, []);

    return (
        <Layout style={{ height: '100vh' }}>
            <Header style={{ height: '40px', background: colorBgContainer, borderBottom: `1px solid ${colorBorder}` }}>
                <TopPanel />
            </Header>
            <Content style={{ height: '100%' }}>
                <Layout style={{ width: '100vw', height: '100%' }}>
                    <Sider width={300} style={{ background: colorBgContainer }}>
                        <LeftPanel setWorkflow={setFile} onBeginEdit={onBeginEdit} />
                    </Sider>
                    {mainView}
                </Layout>
            </Content>
        </Layout>
    );
}
