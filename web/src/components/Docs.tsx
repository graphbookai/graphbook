import React, { useMemo, useState, useEffect, useCallback, useLayoutEffect } from "react";
import { Divider, Flex, Typography, Collapse, theme } from "antd";
import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons";
import { useFilename } from "../hooks/Filename";
import { useAPI } from "../hooks/API";
import { useNodes } from "reactflow";
import type { CollapseProps } from "antd/lib/collapse";
import Markdown from 'react-markdown';
const { useToken } = theme;
const { Text } = Typography;

type NodeDoc = {
    name: string;
    content: string;
};
export function Docs() {
    const { token } = useToken();
    const [hidden, setHidden] = useState(false);
    const [workflowDoc, setWorkflowDoc] = useState(null);
    const [nodeDocs, setNodeDocs] = useState<NodeDoc[]>([]);
    const [windowHeight, setWindowHeight] = useState(0);
    const nodes = useNodes();
    const API = useAPI();
    const filename = useFilename();

    useEffect(() => {
        const loadDocs = async () => {
            if (!API || !filename) {
                return;
            }
            const docs = await API.getWorkflowDoc(filename);
            if (docs?.content) {
                setWorkflowDoc(docs.content);
            }
        };

        loadDocs();
    }, [API, filename]);

    useLayoutEffect(() => {
        const updateWindowHeight = () => {
            setWindowHeight(window.innerHeight);
        };

        window.addEventListener('resize', updateWindowHeight);
        updateWindowHeight();
        return () => window.removeEventListener('resize', updateWindowHeight);
    }, []);

    useEffect(() => {
        if (!nodes || !API) {
            return;
        }

        const loadNodeDocs = async () => {
            const n = nodes as any[];
            const uniqueNodes = new Set(n.map(node => node.data.name));
            const nodeMap = {};
            n.forEach(node => { nodeMap[node.data.name] = node });

            const docs = await Promise.all([...uniqueNodes].map(async (nodeName) => {
                const node = nodeMap[nodeName];
                const doc = node.type === 'step' ? await API.getStepDocstring(nodeName) : await API.getResourceDocstring(nodeName);
                console.log(JSON.stringify(doc?.content));
                return {
                    name: node.data.name,
                    content: doc?.content || '(No docstring)'
                };
            }));
            setNodeDocs(docs);
        };

        loadNodeDocs();
    }, [nodes, API]);

    const containerStyle: React.CSSProperties = useMemo(() => ({
        padding: '5px 10px',
        backgroundColor: token.colorBgBase,
        borderRadius: token.borderRadius,
        color: token.colorTextBase,
        height: windowHeight - 80,
        width: '400px',
    }), [token, windowHeight]);

    const unfoldStyle: React.CSSProperties = useMemo(() => ({
        padding: '10px 5px',
    }), []);

    const docSectionStyle: React.CSSProperties = useMemo(() => ({
        flex: 1,
        height: 0,
        overflow: 'auto',
        border: `1px solid ${token.colorBorder}`,
        borderRadius: token.borderRadius,
    }), [token]);

    const items: CollapseProps['items'] = useMemo(() => {
        return nodeDocs.map((doc, i) => {
            return {
                key: i.toString(),
                label: doc.name,
                children: <Markdown>{doc.content}</Markdown>,
            }
        });
    }, [nodeDocs]);

    if (hidden) {
        return (
            <Clickable>
                <div style={unfoldStyle} onClick={() => setHidden(false)} >
                    <MenuUnfoldOutlined />
                </div>
            </Clickable>
        );
    }

    return (
        <Flex vertical style={containerStyle}>
            <Flex justify="space-between">
                <MenuFoldOutlined onClick={() => setHidden(true)} />
                <Text style={{ fontSize: '1.6em' }}>{filename}</Text>
            </Flex>
            <Divider style={{ margin: '10px 0' }} />
                {
                    workflowDoc &&
                    <div style={{ ...docSectionStyle, padding: '5px', marginBottom: '10px' }}>
                        <Markdown>{workflowDoc}</Markdown>
                    </div>
                }
                {
                    nodeDocs.length > 0 &&
                    <Flex vertical style={{flex: 1, height: 0}}>
                        <Text style={{ padding: '5px', fontSize: '1.2em' }}>Included Nodes</Text>
                        <Collapse style={docSectionStyle} items={items} defaultActiveKey={['0']} />
                    </Flex>
                }
        </Flex>
    );
}

function Clickable({ children }) {
    const [hovered, setHovered] = useState(false);
    const { token } = useToken();

    const onMouseEnter = useCallback(() => {
        setHovered(true);
    }, []);

    const onMouseLeave = useCallback(() => {
        setHovered(false);
    }, []);

    const style = useMemo(() => ({
        backgroundColor: hovered ? token.colorBgLayout : token.colorBgBase,
        transition: 'background-color',
        transitionDuration: '0.2s',
        cursor: 'pointer',
    }), [hovered]);

    return (
        <div style={style} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
            {children}
        </div>
    );
}
