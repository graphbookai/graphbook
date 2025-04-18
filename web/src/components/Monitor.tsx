import React, { useCallback, useMemo, useState, useRef, useEffect } from "react";
import {
    Button,
    Flex,
    Badge,
    Typography,
    Space,
    Table,
    Empty,
    theme,
    Statistic,
    Checkbox,
    Tooltip,
    Dropdown,
    InputNumber,
    Card,
    Image
} from "antd";
import {
    UpOutlined,
    VerticalAlignBottomOutlined,
    CloseOutlined,
    PlusOutlined,
    LeftOutlined,
    RightOutlined,
    QuestionOutlined,
    DownloadOutlined,
    SwapOutlined,
    RotateLeftOutlined,
    RotateRightOutlined,
    ZoomOutOutlined,
    ZoomInOutlined
} from "@ant-design/icons";
import { Resizable } from 're-resizable';
import { getGlobalRunningFile, useRunState } from "../hooks/RunState";
import { useAPIMessageEffect, useAPI } from "../hooks/API";
import { useOnSelectionChange } from "reactflow";
import ReactJson from "@microlink/react-json-view";
import { getMergedLogs, getMediaPath } from "../utils";
import { useFilename } from "../hooks/Filename";
import { useSettings } from "../hooks/Settings";
import type { Node } from "reactflow";
import type { TableProps, StatisticProps, MenuProps } from "antd";

const { Text } = Typography;
const hideHeightThreshold = 20;
const DATA_COLUMNS = ['stats', 'logs', 'data', 'images'];

export function Monitor() {
    const [show, setShow] = useState(false);
    const filename = useFilename();

    const onResize = useCallback((e, direction, ref, d) => {
        if (ref.offsetHeight < hideHeightThreshold) {
            setShow(false);
        }
    }, []);

    const [selectedNodes, setSelectedNodes] = useState<Node[]>([]);
    const onSelectionChange = useCallback(({ nodes }: { nodes: Node[] }) => {
        if (!getGlobalRunningFile() || getGlobalRunningFile() === filename) {
            setSelectedNodes(nodes.filter((node) => node.type === 'step'));
        }
    }, [filename]);
    useOnSelectionChange({
        onChange: onSelectionChange
    });

    return (
        <div>
            {show ? <MonitorView selectedNodes={selectedNodes} onResize={onResize} /> : <HiddenMonitor show={() => setShow(true)} />}
        </div>

    );
};

function HiddenMonitor({ show }) {
    const style: React.CSSProperties = useMemo(() => {
        return {
            position: "absolute",
            bottom: 10,
            right: 'auto',
            left: '50%',
            transform: 'translateX(50%)',
            zIndex: 9,
        };
    }, []);
    const [runState, _] = useRunState();

    return (
        <div style={style}>
            <Badge dot status={runState === 'running' ? 'processing' : 'default'}>
                <Button shape={'circle'} onClick={show} icon={<UpOutlined />} />
            </Badge>
        </div>
    );
}

function MonitorView({ selectedNodes, onResize }) {
    const { token } = theme.useToken();
    const style: React.CSSProperties = useMemo(() => {
        return {
            position: "absolute",
            bottom: 0,
            right: 0,
            left: 0,
            zIndex: 9,
            backgroundColor: token.colorBgBase,
            overflow: "hidden",
            borderLeft: `1px solid ${token.colorBorder}`,
            display: 'flex',
            flexDirection: 'column',
        };
    }, [token]);
    const [runState, _] = useRunState();
    const [nodeStates, setNodeStates] = useState({});
    const [settings, setSettings] = useSettings();
    const viewColumns = settings.monitorDataColumns;
    const filename = useFilename();

    useAPIMessageEffect('stats', (data) => {
        setNodeStates(prev => {
            const newState = { ...prev };
            Object.entries<any>(data).forEach(([key, value]) => {
                newState[key] = {
                    ...newState[key],
                    stats: {
                        ...newState?.[key]?.stats,
                        ...value
                    }
                };
            });
            return newState;
        });
    }, filename);

    useAPIMessageEffect('logs', (data) => {
        setNodeStates(prev => {
            const newState = { ...prev };
            Object.entries<any>(data).forEach(([key, value]) => {
                const prevLogs = newState?.[key]?.logs || [];
                newState[key] = {
                    ...newState[key],
                    logs: getMergedLogs(prevLogs, value)
                };
            });
            return newState;
        });
    }, filename);

    const onScrollToBottomChange = useCallback((e) => {
        setSettings('monitorLogsShouldScrollToBottom', e.target.checked);
    }, []);

    const LogsTitleView = () => {
        return (
            <Space>
                logs |
                <Tooltip title="Scroll to bottom">
                    <Checkbox checked={settings.monitorLogsShouldScrollToBottom} onChange={onScrollToBottomChange}>
                        <VerticalAlignBottomOutlined />
                    </Checkbox>
                </Tooltip>
            </Space>
        );
    };

    const TableHeader = ({ column }: { column: string }) => {
        return (
            <Flex style={{ flex: 1 }} align="center">
                <Flex style={{ padding: '0 10px', flex: 1 }} justify="space-between">
                    {
                        column === 'logs' ? <LogsTitleView /> : <Text>{column}</Text>
                    }
                    <CloseOutlined onClick={() => setSettings('monitorDataColumns', viewColumns.filter((c) => c !== column))} />
                </Flex>
            </Flex>
        );
    };

    const columns: TableProps<any>['columns'] = useMemo(() => {
        const addColumnItems: MenuProps['items'] =
            DATA_COLUMNS
                .filter((column) => !viewColumns.includes(column))
                .map((column, i) => {
                    return {
                        key: i,
                        label: <Text onClick={() => setSettings('monitorDataColumns', [...viewColumns, column])}>{column}</Text>,
                    };
                });
        const columns = [
            {
                title: '',
                dataIndex: 'label',
                key: 'label',
                width: '20px',
                render: (text, record) => {
                    return <Text ellipsis={true}>[{record.key}] {record.label}</Text>;
                }
            },
            ...viewColumns.map((column) => {
                return {
                    title: <TableHeader column={column} />,
                    dataIndex: column,
                    key: column,
                    onHeaderCell: (column) => {
                        return {
                            style: { padding: '0' }
                        };
                    },
                    render: (text, record) => {
                        if (column === 'stats') {
                            return <StatsView data={record[column]} />;
                        }
                        if (column === 'logs') {
                            return <LogsView shouldScrollToBottom={settings.monitorLogsShouldScrollToBottom} data={record[column]} />;
                        }
                        if (column === 'data') {
                            return <DataView stepId={record.key} count={record?.stats?.queue_size} />;
                        }
                        if (column === 'images') {
                            return <DataView stepId={record.key} count={record?.stats?.queue_size} type='image' />;
                        }
                        return <Text>{JSON.stringify(record[column], null, 2)}</Text>;
                    }
                };
            })
        ];
        if (addColumnItems.length > 0) {
            columns.push({
                title: <Dropdown menu={{ items: addColumnItems }}><Button icon={<PlusOutlined />}></Button></Dropdown>,
                dataIndex: 'null',
                key: 'add',
                render: () => (<div />),
                onHeaderCell: (column) => {
                    return {
                        style: { padding: '10px 0px' },
                        children: column.title
                    };
                }
            });
        }
        return columns;
    }, [viewColumns, settings.monitorLogsShouldScrollToBottom]);

    const data: any[] = useMemo(() => {
        return selectedNodes.map((node) => {
            return {
                key: node.id,
                label: node.data.label,
                stats: nodeStates[node.id]?.stats,
                logs: nodeStates[node.id]?.logs,
            };
        });
    }, [selectedNodes, nodeStates]);

    const maxMonitorHeight = useMemo(() => {
        return window.innerHeight - 40;
    }, [window.innerHeight]);

    const monitoredWorkflow = getGlobalRunningFile();

    return (
        <Resizable onResize={onResize} maxHeight={maxMonitorHeight} defaultSize={{ height: 300 }} enable={{ top: true }} style={style} handleStyles={{ top: { backgroundColor: token.colorBorder } }}>
            <Flex justify="center">
                <Space style={{ margin: 10 }}>
                    <Badge status={runState === 'running' ? 'processing' : 'default'} />
                    <Text>Data Monitoring{
                        monitoredWorkflow &&
                        <span>:<Text italic> {monitoredWorkflow}</Text></span>
                    }</Text>

                </Space>
            </Flex>
            {
                selectedNodes.length > 0 ?
                    <Flex vertical style={{ overflowY: 'auto', margin: '0 10px' }}>
                        <Table columns={columns} dataSource={data} pagination={false} />
                    </Flex> :
                    <Flex justify="center" style={{ marginTop: 20 }}>
                        <Empty description={"Select multiple nodes with Ctrl-Click to monitor them"} />
                    </Flex>
            }
        </Resizable>
    );
}

function StatsView({ data }) {
    const { token } = theme.useToken();
    const queueSizeFormatter: StatisticProps['formatter'] = useCallback((value) => {
        return (
            <Space>
                {
                    Object.entries<number>(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, value]) => {
                        return (
                            <Flex key={key} vertical>
                                <div style={{ lineHeight: .5 }}>{value}</div>
                                <Text style={{ display: 'flex', justifyContent: 'right', color: token.colorTextSecondary }}>{key}</Text>
                            </Flex>
                        );
                    })
                }
            </Space>
        )
    }, []);

    return (
        data &&
        <Space align="start" direction="vertical">
            {
                data.record_rate &&
                <Statistic title="Output Rate" value={Math.round(data.record_rate)} suffix="it/s" />
            }
            {
                data.execution !== undefined &&
                <Statistic title="Execution Percentage" value={Math.round(data.execution * 100)} suffix="%" />
            }
            {
                data.queue_size && Object.keys(data.queue_size).length > 0 ?
                    <Statistic title="Queue Size" value={data.queue_size} formatter={queueSizeFormatter} /> : ""
            }
        </Space>
    )
}

function LogsView({ data, shouldScrollToBottom }) {
    const bottomRef = useRef<HTMLDivElement>(null);
    const { token } = theme.useToken();


    useEffect(() => {
        if (shouldScrollToBottom) {
            bottomRef.current?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: 'instant' });
        }
    }, [data, shouldScrollToBottom]);

    const bg = useCallback((i) => {
        return i % 2 === 0 ? token.colorBgBase : token.colorBgLayout;
    }, [token]);

    const textOf = useCallback((t) => {
        if (typeof t === 'string') {
            return t;
        }
        return JSON.stringify(t);
    }, []);

    return (
        !data || data.length === 0 ?
            <Empty description="No logs" /> :
            <Flex vertical style={{ maxHeight: '410px', overflow: 'auto' }}>
                {
                    data.map((log, i) => {
                        const { msg } = log;
                        const style: React.CSSProperties = {
                            backgroundColor: bg(i),
                            margin: '1px 0',
                            fontSize: '.8em',
                            lineHeight: 1,
                            borderLeft: `2px solid ${token.colorBorder}`,
                            padding: '1px 0 1px 4px'
                        };
                        return (
                            <Text key={i} style={style}>{textOf(msg)}</Text>
                        );
                    })
                }
                <div ref={bottomRef} />
            </Flex>
    );
}

type DataViewType = 'default' | 'image';
type DataViewProps = {
    stepId: string,
    count: { [key: string]: number },
    type?: DataViewType,
};
function DataView({ stepId, count, type }: DataViewProps) {
    const [currentIndex, setCurrentIndex] = useState({});
    const [currentImagePreview, setCurrentImagePreview] = useState('');
    const [data, setData] = useState({});
    const API = useAPI();
    const usingToken = theme.useToken();
    const globalTheme = usingToken.theme;
    const [settings, _] = useSettings();
    const { token } = usingToken;
    const filename = useFilename();

    useEffect(() => {
        if (!API || !count) {
            return;
        }
        const initializeKey = async (key) => {
            const res = await (filename.endsWith('.log') ? API.getLog(filename, stepId, key, 0) : API.getState(stepId, key, 0));
            setData((prev) => {
                return {
                    ...prev,
                    [key]: res
                }
            });
            setCurrentIndex((prev) => {
                return {
                    ...prev,
                    [key]: 0
                };
            });
        };
        Object.keys(count).forEach(key => {
            if (currentIndex[key] === undefined) {
                initializeKey(key);
            }
        });

    }, [count, currentIndex, API, filename]);

    const onIndexChange = useCallback(async (key, index) => {
        if (!API) {
            return;
        }
        index = Math.max(0, Math.min(index, count[key] - 1));
        const res = await (filename.endsWith('.log') ? API.getLog(filename, stepId, key, index) : API.getState(stepId, key, index));
        setData((prev) => {
            return {
                ...prev,
                [key]: res
            }
        });
        setCurrentIndex((prev) => {
            return {
                ...prev,
                [key]: index
            };
        });
    }, [count, API, filename]);

    const onDownloadImage = useCallback(() => {
        const url = currentImagePreview;
        fetch(url)
            .then((response) => response.blob())
            .then((blob) => {
                const blobUrl = URL.createObjectURL(new Blob([blob]));
                const link = document.createElement('a');
                link.href = blobUrl;
                const { type } = blob;
                const filename = Date.now() + '.' + type.split('/')[1];
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                URL.revokeObjectURL(blobUrl);
                link.remove();
            });
    }, [currentImagePreview]);

    const views = useMemo(() => {
        const views = {};
        Object.entries<any>(data).map(([pin, d]) => {
            const value = d?.data;
            if (!value) {
                views[pin] = <QuestionOutlined />;
            } else {
                if (!type || type === 'default') {
                    const style = {
                        minWidth: '400px',
                        minHeight: '300px',
                        maxWidth: '400px',
                        maxHeight: '300px',
                        overflow: 'auto',
                    }
                    views[pin] = (
                        <ReactJson
                            style={style}
                            theme={globalTheme.id === 0 ? "rjv-default" : "monokai"}
                            name={false}
                            displayDataTypes={false}
                            indentWidth={2}
                            src={value}
                        />
                    );
                } else if (type === 'image') {
                    const style = {
                        minWidth: '400px',
                        minHeight: '300px',
                        maxWidth: '400px',
                        maxHeight: '300px',
                        overflow: 'hidden',
                        padding: '5px',
                    };
                    const imageEntries = {};
                    Object.entries<any>(value).forEach(([key, value]) => {
                        if (Array.isArray(value)) {
                            const im = value.filter((v) => v.type === 'image');
                            if (im.length > 0) {
                                imageEntries[key] = im;
                            }
                        } else {
                            if (value.type === 'image') {
                                imageEntries[key] = [value];
                            }
                        }
                    });
                    views[pin] = (
                        <Flex style={style} vertical>
                            {
                                Object.entries<any>(imageEntries).map(([key, images]) => {
                                    return (
                                        <Flex key={key} align="center" style={{ border: `1px solid ${token.colorBorder}`, padding: '5px', borderRadius: '5px' }}>
                                            <Text ellipsis={true} style={{ flex: 1 }} >{key}</Text>
                                            <div style={{ flex: 5, flexDirection: "row", overflowX: 'scroll', flexWrap: 'nowrap', whiteSpace: 'nowrap' }}>
                                                <Image.PreviewGroup
                                                    preview={{
                                                        onVisibleChange: (isVisible, __, index) => {
                                                            if (isVisible) {
                                                                setCurrentImagePreview(getMediaPath(settings, images[index]));
                                                            }
                                                        },
                                                        onChange: (index) => {
                                                            setCurrentImagePreview(getMediaPath(settings, images[index]));
                                                        },
                                                        toolbarRender: (
                                                            _,
                                                            {
                                                                transform: { scale },
                                                                actions: {
                                                                    onActive,
                                                                    onFlipY,
                                                                    onFlipX,
                                                                    onRotateLeft,
                                                                    onRotateRight,
                                                                    onZoomOut,
                                                                    onZoomIn,
                                                                }
                                                            }
                                                        ) => (
                                                            <Space className="toolbar-wrapper">
                                                                <LeftOutlined onClick={() => onActive?.(-1)} />
                                                                <RightOutlined onClick={() => onActive?.(1)} />
                                                                <DownloadOutlined onClick={onDownloadImage} />
                                                                <SwapOutlined rotate={90} onClick={onFlipY} />
                                                                <SwapOutlined onClick={onFlipX} />
                                                                <RotateLeftOutlined onClick={onRotateLeft} />
                                                                <RotateRightOutlined onClick={onRotateRight} />
                                                                <ZoomOutOutlined disabled={scale === 1} onClick={onZoomOut} />
                                                                <ZoomInOutlined disabled={scale === 50} onClick={onZoomIn} />
                                                            </Space>
                                                        )
                                                    }}
                                                >
                                                    {
                                                        images.map((image, i) => {
                                                            return (
                                                                <Image height={120} key={i} src={getMediaPath(settings, image)} />
                                                            );
                                                        })
                                                    }
                                                </Image.PreviewGroup>
                                            </div>
                                        </Flex>
                                    );
                                })
                            }
                        </Flex>
                    );
                }
            }
        });
        return views;
    }, [data, globalTheme, currentImagePreview, settings]);

    const cardStyle: React.CSSProperties = useMemo(() => {
        return {
            minWidth: '400px',
            minHeight: '300px',
            maxWidth: '400px',
            maxHeight: '300px',
        };
    }, []);

    return (
        count ?
            <Space align="start">
                {
                    Object.entries<number>(count).sort(([a], [b]) => a.localeCompare(b)).map(([pin, size]) => {
                        return (
                            <Space key={pin} direction="vertical" align="center">
                                <Text>{pin}</Text>
                                <Card style={cardStyle}>
                                    {views[pin]}
                                </Card>
                                <Space>
                                    <Button onClick={() => onIndexChange(pin, currentIndex[pin] - 1)} icon={<LeftOutlined />} shape='circle' />
                                    <Space align="center">
                                        <InputNumber value={currentIndex[pin]} onChange={(value) => onIndexChange(pin, value)} max={size} min={0} controls={false} />
                                        <Text>/ {size - 1}</Text>
                                    </Space>
                                    <Button onClick={() => onIndexChange(pin, currentIndex[pin] + 1)} icon={<RightOutlined />} shape='circle' />
                                </Space>
                            </Space>
                        );
                    })
                }
            </Space> :
            <Empty description="No data" />
    )
}
