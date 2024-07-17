import React, { useCallback, useMemo, useState, useRef, useEffect } from "react";
import { Button, Flex, Badge, Typography, Space, Table, Empty, theme, Statistic, Checkbox, Tooltip, Dropdown } from "antd";
import { UpOutlined, VerticalAlignBottomOutlined, CloseOutlined, PlusOutlined } from "@ant-design/icons";
import { Resizable } from 're-resizable';
import { getGlobalRunningFile, useRunState } from "../hooks/RunState";
import { useAPIMessage } from "../hooks/API";
import { useOnSelectionChange } from "reactflow";
import type { Node } from "reactflow";
import type { TableProps, StatisticProps, MenuProps } from "antd";
import { getMergedLogs } from "../utils";
const { Text } = Typography;
const hideHeightThreshold = 20;
const DATA_COLUMNS = ['stats', 'logs', 'view'];

export function Monitor() {
    const [show, setShow] = useState(true);

    const onResize = useCallback((e, direction, ref, d) => {
        if (ref.offsetHeight < hideHeightThreshold) {
            setShow(false);
        }
    }, []);

    return (
        <div>
            {show ? <MonitorView onResize={onResize} /> : <HiddenMonitor show={() => setShow(true)} />}
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
            <Badge status={runState === 'running' ? 'processing' : 'default'}>
                <Button shape={'circle'} onClick={show} icon={<UpOutlined />} />
            </Badge>
        </div>
    );
}

function MonitorView({ onResize }) {
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
    const [selectedNodes, setSelectedNodes] = useState<Node[]>([]);
    const [viewColumns, setViewColumns] = useState(DATA_COLUMNS);
    const [shouldScrollLogsToBottom, setShouldScrollLogsToBottom] = useState(true);
    const onSelectionChange = useCallback(({ nodes }: { nodes: Node[] }) => {
        setSelectedNodes(nodes.filter((node) => node.type === 'step'));
    }, []);
    useOnSelectionChange({
        onChange: onSelectionChange
    });

    useAPIMessage('stats', (data) => {
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
    });

    useAPIMessage('logs', (data) => {
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
    });

    const onScrollToBottomChange = useCallback((e) => {
        setShouldScrollLogsToBottom(e.target.checked);
    }, []);

    const LogsTitleView = () => {
        return (
            <Space>
                logs |
                <Tooltip title="Scroll to bottom">
                    <Checkbox checked={shouldScrollLogsToBottom} onChange={onScrollToBottomChange}>
                        <VerticalAlignBottomOutlined />
                    </Checkbox>
                </Tooltip>
            </Space>
        );
    };

    const TableHeader = ({ column }: { column: string }) => {
        return (
            <Flex justify="space-between">
                {
                    column === 'logs' ? <LogsTitleView /> : <Text>{column}</Text>
                }
                <CloseOutlined onClick={() => setViewColumns(prev => prev.filter((c) => c !== column))} />
            </Flex>
        );
    }

    const columns: TableProps<any>['columns'] = useMemo(() => {
        const addColumnItems: MenuProps['items'] = 
            DATA_COLUMNS
            .filter((column) => !viewColumns.includes(column))
            .map((column, i) => {
                return {
                    key: i,
                    label: <Text onClick={()=>setViewColumns(prev => [...prev, column])}>{column}</Text>,
                };
            });
        const columns = [
            {
                title: '',
                dataIndex: 'label',
                key: 'label',
                render: (text, record) => {
                    return <Text>[{record.key}] {record.label}</Text>;
                }
            },
            ...viewColumns.map((column) => {
                return {
                    title: <TableHeader column={column} />,
                    dataIndex: column,
                    key: column,
                    render: (text, record) => {
                        if (column === 'stats') {
                            return <StatsView data={record[column]} />;
                        }
                        if (column === 'logs') {
                            return <LogsView shouldScrollToBottom={shouldScrollLogsToBottom} data={record[column]} />;
                        }
                        return <Text>{JSON.stringify(record[column], null, 2)}</Text>;
                    }
                };
            })
        ];
        if (addColumnItems.length > 0) {
            columns.push({
                title: <Dropdown menu={{items: addColumnItems}}><Button icon={<PlusOutlined />}></Button></Dropdown>,
                dataIndex: 'null',
                key: 'add',
                render: () => (<div/>)
            });
        }
        return columns;
    }, [viewColumns, shouldScrollLogsToBottom]);

    const data: any[] = useMemo(() => {
        return selectedNodes.map((node) => {
            return {
                key: node.id,
                label: node.data.label,
                stats: nodeStates[node.id]?.stats,
                logs: nodeStates[node.id]?.logs,
                view: nodeStates[node.id]?.view,
            };
        });
    }, [selectedNodes, nodeStates]);


    return (
        <Resizable onResize={onResize} defaultSize={{ height: 300 }} enable={{ top: true }} style={style} handleStyles={{ top: { backgroundColor: token.colorBorder } }}>
            <Flex justify="center">
                <Space style={{ margin: 10 }}>
                    <Badge status={runState === 'running' ? 'processing' : 'default'} />
                    <Text>Data Monitoring</Text>
                    {
                        runState === 'running' &&
                        <Text italic>(running: {getGlobalRunningFile()})</Text>
                    }
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
    const queueSizeFormatter: StatisticProps['formatter'] = (value) => {
        return (
            <Space>
                {Object.entries(value).map(([key, value]) => {
                    return (
                        <Flex key={key} vertical>
                            <div style={{ lineHeight: .5 }}>{value}</div>
                            <Text style={{ display: 'flex', justifyContent: 'right', color: token.colorBgMask }}>{key}</Text>
                        </Flex>
                    );
                })}
            </Space>
        )
    };
    return (
        data &&
        <Space align="start" size="large">
            {
                data.record_rate &&
                <Statistic title="Output Rate" value={Math.round(data.record_rate)} suffix="notes/s" />
            }
            {
                data.queue_size &&
                <Statistic title="Queue Size" value={data.queue_size} formatter={queueSizeFormatter} />
            }
        </Space>
    )
}

function LogsView({ data, shouldScrollToBottom }) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (shouldScrollToBottom) {
            bottomRef.current?.scrollIntoView({ behavior: 'instant' });
        }
    }, [data, shouldScrollToBottom]);

    return (
        data &&
        (
            <Flex vertical style={{ maxHeight: '200px', overflow: 'auto' }}>
                {
                    data.map((log, i) => {
                        const { msg } = log;
                        return (
                            <Text style={{ fontFamily: 'monospace' }} key={i}>
                                {msg}
                            </Text>
                        );
                    })
                }
                <div ref={bottomRef} />
            </Flex>
        )
    )
}
