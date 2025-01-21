import React, { useMemo, useState, useEffect, useCallback, useLayoutEffect } from "react";
import { Divider, Flex, Typography, Collapse, theme } from "antd";
import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons";
import { useFilename } from "../hooks/Filename";
import { useAPI } from "../hooks/API";
import { useNodes } from "reactflow";
import type { CollapseProps } from "antd/lib/collapse";
import Markdown from 'react-markdown';
import rehypeRaw from 'rehype-raw'
const { useToken } = theme;
const { Text } = Typography;

type NodeDoc = {
    name: string;
    content: string;
};

const DefaultDoc =
    `
### No documentation found.

To add documentation place a markdown file with the same name as the workflow file (with the .md extension) inside your specified docs directory.
By default, this is located in your \`docs/\` directory.

`;

const getExampleStr = (name: string) => {
    return `For example, make a file named \`docs/${name}.md\` and add your documentation there.`;
};

export function Docs({ helpString }: { helpString?: string }) {
    const { token } = useToken();
    const [hidden, setHidden] = useState(false);
    const [nodeDocs, setNodeDocs] = useState<NodeDoc[]>([]);
    const [windowHeight, setWindowHeight] = useState(0);
    const nodes = useNodes();
    const API = useAPI();
    const filename = useFilename();
    const initialDocStr = useMemo(() => helpString ? helpString : DefaultDoc + getExampleStr(filename.split('.')[0]), [filename, helpString]);
    const [workflowDoc, setWorkflowDoc] = useState(initialDocStr);

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

        const n = nodes as any[];
        const uniqueNodeNames = new Set(n.filter(n => n.type === 'step' || n.type === 'resource').map(n => n.data.name));
        const uniqueNodes = [...uniqueNodeNames].map(name => n.find(n => n.data.name === name));

        if (uniqueNodes.length === nodeDocs.length) {
            return;
        }
        
        const currentNodeDocs = uniqueNodes.map(n => {
            return {
                type: n.type,
                name: n.data.name,
                content: n.data.properties?.doc,
            };
        });

        const loadNodeExtraDocs = async () => {
            const extraNodes = currentNodeDocs.filter(n => !n.content);
            if (extraNodes.length === 0) {
                return;
            }
            const nodeDocs = await Promise.all(extraNodes.map(async n => {
                const data = n.type === 'step' ? await API.getStepDocstring(n.name) : await API.getResourceDocstring(n.name);
                return {
                    name: n.name,
                    content: data?.content,
                };
            }));
            const mergedNodeDocs = currentNodeDocs.map(n => {
                const doc = nodeDocs.find(d => d.name === n.name);
                return {
                    type: n.name,
                    name: n.name,
                    content: doc?.content || '(No docstring)',
                };
            });

            setNodeDocs(mergedNodeDocs);
        };

        loadNodeExtraDocs();
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
                <Text style={{ fontSize: '1.6em', marginLeft: 10 }} ellipsis>{filename}</Text>
            </Flex>
            <Divider style={{ margin: '10px 0' }} />
            {
                workflowDoc &&
                <div style={{ ...docSectionStyle, padding: '5px', marginBottom: '10px' }}>
                    <Markdown rehypePlugins={[rehypeRaw]}>{workflowDoc}</Markdown>
                </div>
            }
            {
                nodeDocs.length > 0 &&
                <Flex vertical style={{ flex: 1, height: 0 }}>
                    <Text style={{ padding: '5px', fontSize: '1.2em' }}>Included Nodes</Text>
                    <Collapse size='small' style={docSectionStyle} items={items} defaultActiveKey={['0']} />
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
