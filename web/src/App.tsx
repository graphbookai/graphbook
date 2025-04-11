import React, { useCallback, useEffect, useMemo, useState } from 'react';
import FlowInitializer from './components/Flows/Flow.tsx';
import PyFlowInitializer from './components/Flows/PyFlow.tsx';
import ReadOnlyFlow from './components/Flows/ReadOnlyFlow.tsx';
import { CodeEditor } from './components/Editor/CodeEditor';
import { WelcomeScreen } from './components/WelcomeScreen';
import TopPanel from './components/TopPanel'
import { Layout, ConfigProvider, theme } from 'antd';
import LeftPanel from './components/LeftPanel/LeftPanel';
import { useSettings } from './hooks/Settings';
import { API } from './api';
import { useAPI } from './hooks/API';
import { setGlobalFilename } from './hooks/Filename.ts';
import ErrorBoundary from './components/ErrorBoundary.tsx';

const { Header, Content, Sider } = Layout;

import 'reactflow/dist/style.css';
import './components/Nodes/node.css';


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

type FlowFile = {
    name: string;
    type: 'flow' | 'readonly'
};
function View() {
    const {
        token: { colorBgContainer, colorBorder },
    } = theme.useToken();
    const [codeEditor, setCodeEditor] = useState<{ name: string } | null>(null);
    const [flowFile, setFlowFile] = useState<FlowFile | null>(null);

    const codeEditorView = useMemo(() => {
        if (codeEditor) {
            return <CodeEditor name={codeEditor.name} closeEditor={() => setCodeEditor(null)} />;
        }
        return <></>

    }, [codeEditor]);

    const mainView = useMemo(() => {
        if (flowFile) {
            if (flowFile.type === 'readonly') {
                return (
                    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
                        <ReadOnlyFlow filename={flowFile.name} />
                    </div>
                );
            }

            return (
                <div style={{ width: '100%', height: '100%', position: 'relative' }}>
                    {codeEditorView}
                    {
                        flowFile.name.endsWith('.json') ? <FlowInitializer filename={flowFile.name} /> : <PyFlowInitializer key={flowFile.name} filename={flowFile.name} />
                    }
                </div>
            );
        }

        return <WelcomeScreen />;
    }, [flowFile, codeEditorView]);

    const setFile = useCallback((filename: string) => {
        setFlowFile({ name: filename, type: 'flow' });
        setGlobalFilename(filename);
    }, []);

    const setReadonlyFile = useCallback((filename: string) => {
        setFlowFile({ name: filename, type: 'readonly' });
        setGlobalFilename(filename);
    }, []);

    const setEditCode = useCallback((filename: string) => {
        setCodeEditor({ name: filename });
    }, []);

    return (
        <Layout style={{ height: '100vh' }}>
            <Header style={{ height: '40px', background: colorBgContainer, borderBottom: `1px solid ${colorBorder}` }}>
                <ErrorBoundary horizontal>
                    <TopPanel />
                </ErrorBoundary>
            </Header>
            <Content style={{ height: '100%' }}>
                <Layout style={{ width: '100vw', height: '100%' }}>
                    <Sider width={300} style={{ background: colorBgContainer }}>
                        <LeftPanel setWorkflow={setFile} setExecution={setReadonlyFile} onBeginEdit={setEditCode} />
                    </Sider>
                    <ErrorBoundary key={flowFile?.name}>
                        {mainView}
                    </ErrorBoundary>
                </Layout>
            </Content>
        </Layout>
    );
}
