import React, { useCallback, useState } from 'react';
import Flow from './components/Flow';
import TopPanel from './components/TopPanel'
import { Layout, ConfigProvider, theme } from 'antd';
import LeftPanel from './components/LeftPanel/LeftPanel';
import { Graph } from './graph';

const { Header, Content, Sider } = Layout;

import 'reactflow/dist/style.css';
import { CodeEditor } from './components/Editor/CodeEditor';

export default function App() {

  const [appSettings, setAppSettings] = useState({
    themeAlgorithm: theme.defaultAlgorithm
  });

  return (
    <ConfigProvider
      theme={{
        // 1. Use dark algorithm
        // algorithm: theme.darkAlgorithm,
        algorithm: appSettings.themeAlgorithm

        // 2. Combine dark algorithm and compact algorithm
        // algorithm: [theme.darkAlgorithm, theme.compactAlgorithm],
      }}
    >
      <View setAppSettings={setAppSettings} />
    </ConfigProvider>
  );
}

function View({ setAppSettings }) {
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
        <TopPanel setAppSettings={setAppSettings} />
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
