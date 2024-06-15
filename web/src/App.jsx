import React, { useCallback, useEffect, useState } from 'react';
import Flow from './components/Flow';
import TopPanel from './components/TopPanel'
import { Layout, ConfigProvider, theme } from 'antd';
import LeftPanel from './components/LeftPanel/LeftPanel';
import { Graph } from './graph';
import { useSettings } from './hooks/Settings';
import { API } from './api';

const { Header, Content, Sider } = Layout;

import 'reactflow/dist/style.css';
import { CodeEditor } from './components/Editor/CodeEditor';

export default function App() {
    const [settings, _] = useSettings();
    const [{gsHost, mHost}, setHosts] = useState({gsHost: settings.graphServerHost, mHost: settings.mediaServerHost});
    const themeAlgorithm = settings.theme === "Light" ? theme.defaultAlgorithm : theme.darkAlgorithm;

    useEffect(() => {
        API.connect(gsHost, mHost);
        return () => {
            API.disconnect();
        };
    }, []);

    useEffect(() => {
        const setGraphServerHost = () => {
            API.setHost(settings.graphServerHost);
        };
        if (gsHost !== settings.graphServerHost) {
            setGraphServerHost();
            setHosts({gsHost: settings.graphServerHost, mHost});
        }
        if (mHost !== settings.mediaServerHost) {
            API.setMediaHost(settings.mediaServerHost);
            setHosts({gsHost, mHost: settings.mediaServerHost});
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

    const loadedGraph = Graph.loadGraph();
    const [codeEditor, setCodeEditor] = useState(null);
    const onBeginEdit = useCallback((val) => {
        setCodeEditor(val);
    });


    return (
        <Layout style={{ height: '100vh' }}>
            <Header style={{ height: '40px', background: colorBgContainer, borderBottom: `1px solid ${colorBorder}` }}>
                <TopPanel/>
            </Header>
            <Content style={{ height: '100%' }}>
                <Layout style={{ width: '100vw', height: '100%' }}>
                    <Sider width={300} style={{ background: colorBgContainer }}>
                        <LeftPanel onBeginEdit={onBeginEdit} />
                    </Sider>
                    {codeEditor && <CodeEditor closeEditor={() => setCodeEditor(null)} {...codeEditor} />}
                    <Flow initialNodes={loadedGraph.nodes} initialEdges={loadedGraph.edges} />
                </Layout>
            </Content>
        </Layout>
    );
}
