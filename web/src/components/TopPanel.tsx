

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Popover, Input, Modal, Typography, Space, theme } from 'antd';
import { LinkOutlined, DisconnectOutlined, SettingFilled } from '@ant-design/icons';
import Settings from './Settings';
import { useSettings } from '../hooks/Settings';
import { useAPI, useAPIMessage } from '../hooks/API';
import { SparklineChart, LinearYAxis, LinearYAxisTickSeries, LineSeries, TooltipArea, ChartTooltip } from 'reaviz';
import type { ChartShallowDataShape } from 'reaviz';
import './top-panel.css';

const { Text } = Typography;
const iconStyle = { fontSize: '18px', margin: '0 5px', lineHeight: '40px', height: '100%' };
const connectedStyle = { ...iconStyle, color: 'green' };
const disconnectedStyle = { ...iconStyle, color: 'red' };

export default function TopPanel() {
    const title = 'Graphbook';
    const [settings, setSetting] = useSettings();
    const [connected, setConnected] = useState(false);
    const [host, setHost] = useState(settings.graphServerHost);
    const [hostEditorOpen, setHostEditorOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const API = useAPI();

    useEffect(() => {
        if (!API) {
            setConnected(false);
        } else {
            setConnected(true);
        }
    }, [API]);

    const setAPIHost = useCallback(host => {
        setSetting("graphServerHost", host);
    }, []);

    const onHostChange = useCallback((e) => {
        setHost(e.target.value);
    }, [host]);

    const onOpenChange = useCallback(isOpen => {
        setHostEditorOpen(isOpen);
        if (!isOpen) {
            setAPIHost(host);
        }
    }, [host]);

    const closeAndUpdateHost = useCallback(() => {
        setHostEditorOpen(false);
        setAPIHost(host);
    }, []);

    const setSettingsModal = useCallback((shouldOpen) => {
        setSettingsOpen(shouldOpen);
    }, []);

    const hostEditor = (
        <Input
            onChange={onHostChange}
            onPressEnter={closeAndUpdateHost}
            addonBefore="http://"
            defaultValue={host}
        />
    );

    return (
        <div className="top-panel">
            <div className="textual">
                <h2 className="title">{title}</h2>
                <div style={iconStyle}>
                    <Space>
                        <SparkChart dataLabel="cpu" />
                        <SparkChart dataLabel="mem" />
                        <GPUSparkCharts />
                    </Space>

                    <SettingFilled style={iconStyle} onClick={() => setSettingsModal(true)} />
                    <Popover content={hostEditor} title="Host" placement="leftTop" onOpenChange={onOpenChange} open={hostEditorOpen}>
                        {connected ? <LinkOutlined style={connectedStyle} /> : <DisconnectOutlined style={disconnectedStyle} />}
                    </Popover>
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
