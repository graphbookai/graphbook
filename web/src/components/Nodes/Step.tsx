import React, { CSSProperties, useCallback, useEffect, useMemo, useState } from 'react';
import { Handle, Position, useNodes, useEdges, useReactFlow, useOnSelectionChange } from 'reactflow';
import { Card, Collapse, Badge, Flex, Button, Image, Tabs, theme, Space, Typography } from 'antd';
import { SearchOutlined, FileTextOutlined, CaretRightOutlined, FileImageOutlined, CodeOutlined } from '@ant-design/icons';
import { Widget, isWidgetType } from './widgets/Widgets';
import { Graph } from '../../graph';
import { useRunState } from '../../hooks/RunState';
import { useAPI, useAPINodeMessage } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { nodeBorderStyle } from '../../styles';
import { getMergedLogs, getMediaPath } from '../../utils';
import { useNotification } from '../../hooks/Notification';
import { useSettings } from '../../hooks/Settings';
import { SerializationErrorMessages } from '../Errors';
import { Prompt } from './widgets/Prompts';
import { InputHandle, OutputHandle } from './Handle';
import ReactJson from '@microlink/react-json-view';
import type { LogEntry, Parameter, ImageRef } from '../../utils';
import { Node } from './NodeAPI';

const { Panel } = Collapse;
const { useToken } = theme;
const { Text } = Typography;

type QuickViewEntry = {
    [key: string]: any;
};

export function Step({ id, data, selected }) {
    const { name, parameters, inputs, outputs, isCollapsed } = data;
    const [settings, _] = useSettings();
    const requiresInput = inputs.length > 0;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const [logsData, setLogsData] = useState<LogEntry[]>([]);
    const [errored, setErrored] = useState<boolean>(false);
    const filename = useFilename();

    useAPINodeMessage('view', id, filename, (msg) => {
        // console.log(msg);
        setQuickViewData(msg);
    });

    useAPINodeMessage('logs', id, filename, useCallback((newEntries) => {
        setLogsData(prev => getMergedLogs(prev, newEntries));
    }, [setLogsData]));

    const tabs = useMemo(() => {
        console.log(quickViewData)
        return [{
            label: 'Data',
            children: <DataView data={quickViewData} /> // <CodeOutlined />
        }, {
            label: 'Images',
            children: <ImagesView data={quickViewData} />
        }, {
            label: 'Logs',
            children: <LogsView data={logsData} />
        }]
    }, [quickViewData, logsData]);

    // icon: <FileImageOutlined />,
    // children: (
    //     <EntryImages
    //         style={{ maxHeight: '200px', overflow: 'auto' }}
    //         entry={noteData}
    //     />

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
            requiresInput={requiresInput}
            parameters={parameters}
            outputs={outputs}
            selected={selected}
            errored={errored}
            isCollapsed={isCollapsed}
            tabs={tabs}
        />
    )
}

function DataView({ data }) {
    const globalTheme = theme.useToken().theme;
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]))

    return (
        <div>
            {
                Object.keys(data).length === 0 ?
                'No data' :
                values.map(([key, value], i) => {
                    return (
                        <div>
                            <Text style={{fontSize: '.6em', fontWeight: 'bold'}}>{key}</Text>
                            <ReactJson
                                style={{ maxHeight: '200px', overflow: 'auto', fontSize: '0.6em' }}
                                theme={globalTheme.id === 0 ? "rjv-default" : "monokai"}
                                name={false}
                                displayDataTypes={false}
                                indentWidth={2}
                                src={value}
                            />
                        </div>
                    );
                })
            }
        </div>
    );
}

function LogsView({ data }) {
    return (
        <div>
            {
                data.length === 0 ?
                'No logs yet' :
                (
                    <div style={{ maxHeight: '200px', overflow: 'auto' }}>
                        {
                            data.map((log, i) => {
                                const { msg } = log;
                                return (
                                    <p style={{ fontFamily: 'monospace' }} key={i}>
                                        {JSON.stringify(msg)}
                                    </p>
                                );
                            })
                        }
                    </div>
                )
            }
        </div>
    );
}

function ImagesView({ data }) {
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]));

    return (
        <div>
            {
                Object.keys(data).length === 0 ?
                'No images' :
                values.map(([key, value], i) => (
                    <div>
                        <Text style={{fontSize: '.6em', fontWeight: 'bold'}}>{key}</Text>
                        <ImagesEntry key={key} data={value} />
                    </div>
                ))
            }
        </div>
    ); 
}

function ImagesEntry({ data }) {
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]));
    const [settings, _] = useSettings();

    const imageEntries = useMemo(() => {
        let entries: { [key: string]: ImageRef[] } = {};
        values.forEach(([key, item]) => {
            console.log(item);
            let imageItems: any = [];
            if (Array.isArray(item)) {
                imageItems = item.filter(item => item.type?.slice(0, 5) === 'image');
            } else {
                if (item.type?.slice(0, 5) === 'image') {
                    imageItems.push(item);
                }
            }
            if (imageItems.length > 0) {
                entries[key] = imageItems;
            }
        });
        return entries;
    }, [values]);

    return (
        <Flex>
            {
                Object.keys(imageEntries).length === 0 ?
                'No images' :
                Object.entries<ImageRef[]>(imageEntries).map(([key, images]) => {
                    return (
                        <Space key={key} direction="vertical" align='center'>
                            <Text style={{fontSize: '.6em'}}>{key}</Text>
                            <Flex vertical>
                                {
                                    images.map((image, i) => (
                                        <Image key={i} src={getMediaPath(settings, image)} height={settings.quickviewImageHeight} />
                                    ))
                                }
                            </Flex>
                        </Space>
                    );
                })
            }
        </Flex>
    );
}
