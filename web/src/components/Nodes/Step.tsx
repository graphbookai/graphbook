import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Flex, Image, theme, Typography } from 'antd';
import { useAPINodeMessage } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { getMergedLogs, getMediaPath } from '../../utils';
import { useSettings } from '../../hooks/Settings';
import { usePrompt, Prompt } from '../../hooks/Prompts';
import ReactJson from '@microlink/react-json-view';
import type { LogEntry, ImageRef } from '../../utils';
import { Node, EmptyTab } from './Node';
import Icon, { PictureOutlined, FileTextOutlined } from '@ant-design/icons';
import { Prompt as PromptWidget } from './widgets/Prompts';

const { useToken } = theme;
const { Text } = Typography;

type QuickViewEntry = {
    [key: string]: any;
};

export function Step({ id, data, selected }) {
    const { name, parameters, inputs, outputs, isCollapsed } = data;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const [logsData, setLogsData] = useState<LogEntry[]>([]);
    const [errored, setErrored] = useState<boolean>(false);
    const [recordCount, setRecordCount] = useState({});
    const [isPromptNode, setIsPromptNode] = useState(false);
    const [prompt, setPrompt] = useState<Prompt | null>(null);
    const filename = useFilename();

    useAPINodeMessage('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });

    useAPINodeMessage('logs', id, filename, useCallback((newEntries) => {
        setLogsData(prev => getMergedLogs(prev, newEntries));
    }, [setLogsData]));

    useAPINodeMessage('stats', id, filename, (msg) => {
        setRecordCount(msg.queue_size || {});
    });

    const setSubmitted = usePrompt(id, (prompt) => {
        setPrompt(prompt);
    });

    useEffect(() => {
        if (prompt && prompt.type !== null) {
            setIsPromptNode(true);
        }
    }, [prompt]);

    const tabs = useMemo(() => {
        const t = [{
            label: 'Data',
            children: <DataView data={quickViewData} />,
            icon: <Icon component={Braces} />
        }, {
            label: 'Images',
            children: <ImagesView data={quickViewData} />,
            icon: <PictureOutlined />
        }, {
            label: logsData.length === 0 ? 'Logs' : `Logs (${logsData.length})`,
            children: <LogsView data={logsData} />,
            icon: <FileTextOutlined />
        }];
        if (isPromptNode) {
            t.push({
                label: 'Prompts',
                children: <PromptView nodeId={id} prompt={prompt} setSubmitted={setSubmitted}/>,
                icon: <Click />
            });
        }
        return t;
    }, [quickViewData, logsData, isPromptNode, prompt, setSubmitted]);

    useEffect(() => {
        for (const log of logsData) {
            if (log.type === 'error') {
                setErrored(true);
                return;
            }
        }

        setErrored(false);
    }, [logsData]);

    return (
        <Node
            id={id}
            name={name}
            inputs={inputs}
            parameters={parameters}
            outputs={outputs.map(o => ({ id: o, label: o, recordCount: recordCount[o] }))}
            selected={selected}
            errored={errored}
            isCollapsed={isCollapsed}
            tabs={tabs}
        />
    );
}

function DataView({ data }) {
    const globalTheme = theme.useToken().theme;
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]))

    return (
        <Flex vertical>
            {
                Object.keys(data).length === 0 ?
                    <EmptyTab /> :
                    values.map(([key, value]) => {
                        return (
                            <Flex key={key} vertical>
                                <Text style={{ fontSize: '.6em', fontWeight: 'bold' }}>{key}</Text>
                                <ReactJson
                                    style={{ fontSize: '0.6em' }}
                                    theme={globalTheme.id === 0 ? "rjv-default" : "monokai"}
                                    name={false}
                                    displayDataTypes={false}
                                    indentWidth={2}
                                    src={value}
                                />
                            </Flex>
                        );
                    })
            }
        </Flex>
    );
}

function LogsView({ data }) {
    const { token } = useToken();
    const bottomRef = useRef<HTMLDivElement>(null);
    const shouldScrollToBottom = true;

    useEffect(() => {
        if (shouldScrollToBottom) {
            bottomRef.current?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: 'instant' });
        }
    }, [shouldScrollToBottom, data]);

    const bg = useCallback((i) => {
        return i % 2 === 0 ? token.colorBgBase : token.colorBgLayout;
    }, [token]);

    return (
        data.length === 0 ?
            <EmptyTab description='No logs' /> :
            <Flex vertical>
                {
                    data.map((log, i) => {
                        const { msg } = log;
                        const style: React.CSSProperties = {
                            backgroundColor: bg(i),
                            margin: '1px 0',
                            fontSize: '.6em',
                            lineHeight: 1,
                            borderLeft: `2px solid ${token.colorBorder}`,
                            padding: '1px 0 1px 4px'
                        };
                        return (
                            <Text key={i} style={style}>{msg}</Text>
                        );
                    })
                }
                <div ref={bottomRef} />
            </Flex>
    );
}

function ImagesView({ data }) {
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]));
    const [settings, _] = useSettings();

    const imageEntries = useMemo(() => {
        let entries: { [key: string]: ImageRef[] } = {};
        values.forEach(([outputKey, note]) => {
            Object.entries(note).forEach(([key, item]) => {
                let imageItems: any = [];
                if (Array.isArray(item)) {
                    imageItems = item.filter(item => item.type?.slice(0, 5) === 'image');
                } else {
                    if (item.type?.slice(0, 5) === 'image') {
                        imageItems.push(item);
                    }
                }
                if (imageItems.length > 0) {
                    entries[`${outputKey}/${key}`] = imageItems;
                }
            })
        });
        return entries;
    }, [values]);

    return (
        Object.keys(imageEntries).length === 0 ?
            <EmptyTab description='No images' /> :
            Object.entries(imageEntries).map(([key, value]) => (
                <Flex vertical key={key}>
                    <Text style={{ fontSize: '.6em', fontWeight: 'bold' }}>{key}</Text>
                    <Flex>
                        {
                            value.map((image, i) => (
                                <Image key={i} src={getMediaPath(settings, image)} height={settings.quickviewImageHeight} />
                            ))
                        }
                    </Flex>
                </Flex>
            ))
    );
}

function PromptView({ nodeId, prompt, setSubmitted }) {
    if (!prompt || prompt.type === null) {
        return <EmptyTab description='No prompts available' />;
    }

    return (
        <div className="widgets">
            <PromptWidget nodeId={nodeId} prompt={prompt} setSubmitted={setSubmitted} />
        </div>
    );
}

const Braces = () => (
    <svg width="1em" height="1em" fill="currentColor" viewBox="0 0 24 24">
        <path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4a2 2 0 0 0-2 2v3a2 3 0 0 1-2 3a2 3 0 0 1 2 3v3a2 2 0 0 0 2 2M17 4a2 2 0 0 1 2 2v3a2 3 0 0 0 2 3a2 3 0 0 0-2 3v3a2 2 0 0 1-2 2"></path>
    </svg>
);

const Click = () => (
    <svg width="1em" height="1em" viewBox="0 0 24 24" style={{ margin: '2px 0 0 0', display: 'block' }}>
        <g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
            <path d="M8 13V4.5a1.5 1.5 0 0 1 3 0V12m0-.5v-2a1.5 1.5 0 0 1 3 0V12m0-1.5a1.5 1.5 0 0 1 3 0V12"></path>
            <path d="M17 11.5a1.5 1.5 0 0 1 3 0V16a6 6 0 0 1-6 6h-2h.208a6 6 0 0 1-5.012-2.7L7 19q-.468-.718-3.286-5.728a1.5 1.5 0 0 1 .536-2.022a1.87 1.87 0 0 1 2.28.28L8 13M5 3L4 2m0 5H3m11-4l1-1m0 4h1"></path>
        </g>
    </svg>
);
