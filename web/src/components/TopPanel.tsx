

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Popover, Modal, Typography, Space, Popconfirm, theme } from 'antd';
import { LinkOutlined, DisconnectOutlined, SettingFilled, QuestionCircleOutlined } from '@ant-design/icons';
import Settings from './Settings';
import { useAPI, useAPIMessage, useAPIReconnectTimer } from '../hooks/API';
import { SparklineChart, LinearYAxis, LinearYAxisTickSeries, LinearXAxis, LinearXAxisTickSeries, LineSeries, TooltipArea, ChartTooltip, StackedBarChart, StackedBarSeries, Bar } from 'reaviz';
import type { ChartShallowDataShape, ChartNestedDataShape } from 'reaviz';
import './top-panel.css';

const { Text, Link } = Typography;
const iconStyle = { fontSize: '18px', margin: '0 5px', lineHeight: '40px', height: '100%' };
const connectedStyle = { ...iconStyle, color: 'green' };
const disconnectedStyle = { ...iconStyle, color: 'red' };

export default function TopPanel() {
    const title = 'Graphbook';
    const [connected, setConnected] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [popconfirmOpen, setPopconfirmOpen] = useState(false);
    const reconnectTime = useAPIReconnectTimer();
    const API = useAPI();

    useEffect(() => {
        if (!API) {
            setConnected(false);
            setPopconfirmOpen(true);
        } else {
            setConnected(true);
            setPopconfirmOpen(false);
        }
    }, [API]);


    const setSettingsModal = useCallback((shouldOpen) => {
        setSettingsOpen(shouldOpen);
    }, []);

    const closePopconfirm = useCallback(() => {
        setPopconfirmOpen(false);
    }, []);


    return (
        <div className="top-panel">
            <div className="textual">
                <h2 className="title">{title}</h2>
                <div style={iconStyle}>
                    <Space>
                        <WorkerChart />
                        <SparkChart dataLabel="cpu" />
                        <SparkChart dataLabel="mem" />
                        <GPUSparkCharts />
                    </Space>

                    <SettingFilled style={iconStyle} onClick={() => setSettingsModal(true)} />
                    <HelpMenu />
                    {connected ?
                        <LinkOutlined style={connectedStyle} /> :
                        <Popconfirm
                            placement="bottomRight"
                            title={"Disconnected"}
                            description={`Graphbook is not connected to the server. Attempting to reconnect in ${reconnectTime} seconds.`}
                            okText="Ok"
                            showCancel={false}
                            open={popconfirmOpen}
                            onConfirm={closePopconfirm}
                        >
                            <DisconnectOutlined style={disconnectedStyle} />
                        </Popconfirm>
                    }
                </div>
            </div>

            <Modal width={1000} title="Settings" open={settingsOpen} onCancel={() => setSettingsModal(false)} footer={null}>
                <Settings />
            </Modal>
        </div>
    )
}

const SPARK_SIZE_LIMIT = 20;
type SparkChartProps = { dataLabel: string };
type GPUData = {
    id: string;
    name: string;
    util: number;
    mem: number;
};
function GPUSparkCharts() {
    const [util, setUtil] = useState<{ [id: string]: ChartShallowDataShape[] }>({});
    const [mem, setMem] = useState<{ [id: string]: ChartShallowDataShape[] }>({});
    const { token } = theme.useToken();
    const updateData = useCallback(data => {
        const gpuUsage: GPUData[] = data.gpu;
        const dateNow = new Date();
        setUtil(prev => {
            const newUtil = { ...prev };
            gpuUsage.forEach(usage => {
                newUtil[usage.id] = [...(newUtil[usage.id] || []), { key: dateNow, data: usage.util }];
                if (newUtil[usage.id].length > SPARK_SIZE_LIMIT) {
                    newUtil[usage.id].shift();
                }
            });

            return newUtil;
        });
        setMem(prev => {
            const newMem = { ...prev };
            gpuUsage.forEach(usage => {
                newMem[usage.id] = [...(newMem[usage.id] || []), { key: dateNow, data: Math.round(usage.mem) }];
                if (newMem[usage.id].length > SPARK_SIZE_LIMIT) {
                    newMem[usage.id].shift();
                }
            });

            return newMem;
        });
    }, []);

    useAPIMessage('system_util', updateData);

    const YAxis = useMemo(() => {
        return (
            <LinearYAxis type="value" domain={[0, 100]} axisLine={null} tickSeries={<LinearYAxisTickSeries line={null} label={null} />} />
        )
    }, []);

    const Series = useMemo(() => {
        return (
            <LineSeries animated={false} tooltip={
                <TooltipArea
                    tooltip={
                        <ChartTooltip content={(data) => (<Text>{data.y}</Text>)} />
                    }
                />
            } />
        );
    }, []);

    return (
        <Space>
            {Object.keys(util).map((id) => {
                if (!util[id] || !mem[id]) return null;

                return (
                    <div key={id} style={{ position: 'relative' }}>
                        <Text style={{ position: 'absolute', top: 0, left: 1, fontSize: '8px' }}>GPU {id}</Text>
                        <Space style={{ display: 'inline-flex', border: `1px solid ${token.colorBorder}`, height: '38px' }}>
                            <Text>UTIL</Text>
                            <div style={{ border: `1px solid ${token.colorBorder}` }}>
                                <SparklineChart
                                    series={Series}
                                    yAxis={YAxis}
                                    data={util[id]}
                                    width={40}
                                    height={30}
                                />
                            </div>
                            <Text>MEM</Text>
                            <div style={{ border: `1px solid ${token.colorBorder}` }}>
                                <SparklineChart
                                    series={Series}
                                    yAxis={YAxis}
                                    data={mem[id]}
                                    width={40}
                                    height={30}
                                />
                            </div>
                        </Space>
                    </div>
                )
            })}
        </Space>
    );
}

function SparkChart({ dataLabel }: SparkChartProps) {
    const [data, setData] = useState<ChartShallowDataShape[]>([]);
    const { token } = theme.useToken();

    const updateData = useCallback(data => {
        setData(prev => {
            const newData = [
                ...prev,
                {
                    data: data[dataLabel],
                    key: new Date()
                }
            ];
            if (newData.length > SPARK_SIZE_LIMIT) {
                newData.shift();
            }
            return newData;
        });
    }, [dataLabel]);

    useAPIMessage('system_util', updateData);

    const Series = useMemo(() => {
        return (
            <LineSeries animated={false} tooltip={
                <TooltipArea
                    tooltip={
                        <ChartTooltip content={(data) => (<Text>{data.y}</Text>)} />
                    }
                />
            } />
        );
    }, []);

    const YAxis = useMemo(() => {
        return (
            <LinearYAxis type="value" domain={[0, 100]} axisLine={null} tickSeries={<LinearYAxisTickSeries line={null} label={null} />} />
        )
    }, []);

    return (
        <Space style={{ display: 'inline-flex' }} align="center">
            <Text>{dataLabel.toUpperCase()}</Text>
            <div style={{ border: `1px solid ${token.colorBorder}` }}>
                <SparklineChart
                    series={Series}
                    yAxis={YAxis}
                    data={data}
                    width={40}
                    height={30}
                />
            </div>
        </Space>
    );
}

function WorkerChart() {
    const [data, setData] = useState<ChartNestedDataShape[]>([]);
    const { token } = theme.useToken();

    const updateData = useCallback(data => {
        setData(prev => {
            const queueSizes = data.worker_queue_sizes;
            if (queueSizes) {
                const enqueuedSize =
                    queueSizes.dump.reduce((acc, val) => acc + val, 0) +
                    queueSizes.load.reduce((acc, val) => acc + val, 0);
                const outgoingSize =
                    queueSizes.load_result.reduce((acc, val) => acc + val, 0) +
                    queueSizes.dump_result.reduce((acc, val) => acc + val, 0);
                const newData = [
                    ...prev,
                    {
                        data: [{
                            key: 'enqueued',
                            data: -Math.min(enqueuedSize, 32)
                        }, {
                            key: 'outgoing',
                            data: Math.min(outgoingSize, 32)
                        }],
                        key: new Date()
                    }
                ];
                if (newData.length > SPARK_SIZE_LIMIT) {
                    newData.shift();
                }
                return newData;
            }
            return prev;

        });
    }, []);

    useAPIMessage('system_util', updateData);

    const Series = useMemo(() => {
        return (
            <StackedBarSeries
                type="stackedDiverging"
                animated={false}
                tooltip={null}
                bar={<Bar gradient={null} />}
                colorScheme={['#E84045', '#32E845']}
                padding={0}
            />
        );
    }, []);

    const XAxis = useMemo(() => {
        return (
            <LinearXAxis type="category" position="center" tickSeries={<LinearXAxisTickSeries line={null} label={null} />} />
        );
    }, []);

    const YAxis = useMemo(() => {
        return (
            <LinearYAxis type="value" axisLine={null} tickSeries={<LinearYAxisTickSeries line={null} label={null} />} />
        )
    }, []);

    return (
        <Space style={{ display: 'inline-flex' }} align="center">
            <Text>WORKERS</Text>
            <div style={{ border: `1px solid ${token.colorBorder}` }}>
                <StackedBarChart
                    series={Series}
                    gridlines={null}
                    xAxis={XAxis}
                    yAxis={YAxis}
                    data={data}
                    width={40}
                    height={30}
                    margins={0}
                />
            </div>
        </Space>
    );
}

function HelpMenu() {
    const content = useMemo(() => (
        <div>
            <Text><Text strong>LMB (x2)</Text> or <Text strong>Ctrl + Space</Text> to search</Text>
            <br />
            <Text><Text strong>DEL</Text> to delete selected node or edge</Text>
            <br />
            <Text><Text strong>SHIFT + LMB</Text> to drag and select</Text>
            <br />
            <Text><Text strong>CTRL + LMB</Text> to select multiple</Text>
            <br />
            <Link href="https://docs.graphbook.ai" target="_blank">See docs</Link>
        </div>
    ), []);

    return (
        <Popover
            title="Help"
            content={content}
        >
            <QuestionCircleOutlined style={iconStyle} />
        </Popover>
    );

}
