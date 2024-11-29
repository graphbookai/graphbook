import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Flex, Image, theme, Typography } from 'antd';
import { useAPINodeMessage } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { getMergedLogs, getMediaPath } from '../../utils';
import { useSettings } from '../../hooks/Settings';
import ReactJson from '@microlink/react-json-view';
import type { LogEntry, ImageRef } from '../../utils';
import { Node, EmptyTab } from './NodeAPI';

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
    const filename = useFilename();

    useAPINodeMessage('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });

    useAPINodeMessage('logs', id, filename, useCallback((newEntries) => {
        setLogsData(prev => getMergedLogs(prev, newEntries));
    }, [setLogsData]));

    const tabs = useMemo(() => {
        return [{
            label: 'Data',
            children: <DataView data={quickViewData} /> // <CodeOutlined />
        }, {
            label: 'Images',
            children: <ImagesView data={quickViewData} />
        }, {
            label: logsData.length === 0 ? 'Logs' : `Logs (${logsData.length})`,
            children: <LogsView data={logsData} />
        }]
    }, [quickViewData, logsData]);

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
            outputs={outputs.map(o => ({id: o, label: o}))}
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
                            <Text style={{fontSize: '.6em', fontWeight: 'bold'}}>{key}</Text>
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
            bottomRef.current?.scrollIntoView({block: "nearest", inline: "nearest", behavior: 'instant' });
        }
    }, [shouldScrollToBottom, data]);

    const bg = useCallback((i) => {
        return i % 2 === 0 ? token.colorBgBase : token.colorBgLayout;
    }, [token]);

    return (
        data.length === 0 ?
        <EmptyTab description='No logs'/> :
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
        <EmptyTab description='No images'/> :
        Object.entries(imageEntries).map(([key, value]) => (
            <Flex vertical key={key}>
                <Text style={{fontSize: '.6em', fontWeight: 'bold'}}>{key}</Text>
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
